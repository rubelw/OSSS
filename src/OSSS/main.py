# src/OSSS/main.py
from __future__ import annotations

import os
import socket
import time
import logging
import httpx
import json
import pathlib
import yaml
import logging.config
import sqlalchemy as sa
import inspect as _pyinspect
from contextlib import asynccontextmanager
from fastapi import FastAPI, APIRouter, Depends, Request, HTTPException
from fastapi.routing import APIRoute

from starlette.middleware.sessions import SessionMiddleware

from sqlalchemy.orm import class_mapper
from sqlalchemy.orm.exc import UnmappedClassError
from sqlalchemy.inspection import inspect as sa_inspect

from OSSS.core.config import settings
from OSSS.db import get_sessionmaker

from OSSS.middleware.session_ttl import SessionTTL

from OSSS.api.generated_resources.register_all import generate_routers_for_all_models
from OSSS.api.routers.auth_flow import router as auth_router
from OSSS.api import debug
from OSSS.api import auth_proxy
from OSSS.api.routers.me import router as me_router
from OSSS.api.routers.health import router as health_router
from OSSS.api.logout import router as logout_router
from consul import Consul

# New auth deps
from OSSS.auth.deps import ensure_access_token, get_current_user

from OSSS.sessions import (
    attach_session_store,
    get_session_store,
    SESSION_PREFIX,
    ensure_sid_cookie_and_store,
    RedisSession,
    probe_key_ttl,
    refresh_access_token,  # <-- needed for proactive refresh
)

from OSSS.sessions_diag import router as sessions_diag_router
from OSSS.app_logger import get_logger
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from starlette.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from pythonjsonlogger import jsonlogger

# If you might be on Postgres/asyncpg, these imports let us detect specific violation types
try:
    from asyncpg.exceptions import (
        UniqueViolationError,
        ForeignKeyViolationError,
        NotNullViolationError,
        CheckViolationError,
    )
    _HAS_ASYNCPG = True
except Exception:  # pragma: no cover
    _HAS_ASYNCPG = False

# --- BEGIN: verbose OIDC helpers imports ---
from typing import Optional
from urllib.parse import urljoin
# --- END: verbose OIDC helpers imports ---


LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()" : "pythonjsonlogger.jsonlogger.JsonFormatter",
            # include fields you want searchable in ES
            "fmt": "%(asctime)s %(levelname)s %(name)s %(message)s %(process)d %(thread)d %(module)s %(pathname)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
            "stream": "ext://sys.stdout",
        },
    },
    "loggers": {
        # send everything to the JSON console handler
        "":               {"handlers": ["console"], "level": "INFO"},
        "uvicorn":        {"handlers": ["console"], "level": "INFO", "propagate": False},
        "uvicorn.error":  {"handlers": ["console"], "level": "INFO", "propagate": False},
        "uvicorn.access": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "startup":        {"handlers": ["console"], "level": "DEBUG", "propagate": False},
    },
}

logging.config.dictConfig(LOGGING)
log = logging.getLogger("main")

# For Consul
#CONSUL_HOST = os.getenv("CONSUL_HOST", "127.0.0.1")
CONSUL_HOST="host.docker.internal"
CONSUL_PORT = int(os.getenv("CONSUL_PORT", "8500"))

APP_HOST = os.getenv("APP_HOST", "host.docker.internal")
APP_PORT = int(os.getenv("APP_PORT", "8081"))
SERVICE_NAME = os.getenv("SERVICE_NAME", "osss-api")
SERVICE_ID = os.getenv("SERVICE_ID", f"{SERVICE_NAME}-{socket.gethostname()}-{APP_PORT}")

def consul_client() -> Consul:
    return Consul(host=CONSUL_HOST, port=CONSUL_PORT)

def pick_healthy_service(consul: Consul, name: str) -> tuple[str, int]:
    _i, nodes = consul.health.service(name, passing=True)
    if not nodes:
        raise HTTPException(status_code=503, detail=f"No healthy instances for {name}")
    svc = nodes[0]["Service"]  # naive pick; could add round-robin later
    return svc["Address"], svc["Port"]



def _discover_Base():
    """Best-effort discovery of the SQLAlchemy Declarative Base."""
    candidates = [
        "OSSS.db.base:Base",
        "OSSS.db.models.base:Base",
        "OSSS.db.models:Base",
    ]
    last_err = None
    for cand in candidates:
        try:
            mod, attr = cand.split(":")
            m = __import__(mod, fromlist=[attr])
            Base = getattr(m, attr)
            if getattr(getattr(Base, "registry", None), "mappers", None) is not None:
                return Base, None
        except Exception as e:
            last_err = str(e)
            continue
    return None, last_err or "No suitable Base found"


def _dump_mappings(header: str = "[mappings]") -> None:
    """Emit a detailed list of mapped classes, highlighting entity_tags."""
    Base, err = _discover_Base()
    if not Base:
        log.warning("%s could not discover Base: %s", header, err)
        return
    try:
        mappers = list(Base.registry.mappers)  # type: ignore[attr-defined]
    except Exception as e:
        log.exception("%s failed to enumerate mappers: %s", header, e)
        return

    if not mappers:
        log.warning("%s no mappers registered yet", header)
        return

    log.info("%s %d mapped classes:", header, len(mappers))
    found_entity_tags = False

    for mp in sorted(mappers, key=lambda m: m.class_.__name__):
        cls = mp.class_
        name = cls.__name__
        tablename = getattr(cls, "__tablename__", "<none>")
        try:
            mapper_info = sa_inspect(cls)
            cols = [c.key for c in mapper_info.columns]
            pks = [c.key for c in mapper_info.primary_key]
        except Exception:
            cols, pks = ["<inspect-failed>"], ["<inspect-failed>"]
        composite_pk = len(pks) > 1
        flag = ""
        if tablename == "entity_tags" or "entitytag" in name.lower():
            flag = "  <-- entity_tags?"
            found_entity_tags = True
        log.info(
            "  - %s (table=%s) PK=%s composite=%s cols=%s%s",
            name, tablename, pks, composite_pk, cols, flag
        )

    if not found_entity_tags:
        log.warning("%s entity_tags not found among mapped classes", header)


if os.getenv("OSSS_DEBUG_MAPPINGS") == "1":
    try:
        from OSSS.db.models.ap_vendors import ApVendor, ApVendorBase  # type: ignore
        assert ApVendor.__mapper__.class_ is ApVendor
        try:
            class_mapper(ApVendorBase)
            raise AssertionError("Mixin is incorrectly mapped!")
        except UnmappedClassError:
            pass
    except Exception as e:
        log.debug("[mappings] ApVendor sanity check skipped: %s", e)

    _dump_mappings("[mappings][import-time]")


def generate_unique_id(route: APIRoute) -> str:
    methods = "_".join(sorted((route.methods or []), key=str.lower)).lower()
    path = route.path_format.replace("/", "_").replace("{", "").replace("}", "").strip("_")
    tag = (route.tags[0] if route.tags else "default").lower().replace(" ", "_")
    return f"{tag}__{methods}__{path}"


def _routes_signature(router: APIRouter) -> set[tuple[str, tuple[str, ...]]]:
    sig: set[tuple[str, tuple[str, ...]]] = set()
    for r in router.routes:
        if isinstance(r, APIRoute):
            methods = tuple(sorted((r.methods or [])))
            sig.add((r.path, methods))
    return sig


def _cfg(lower: str, UPPER: str, default=None):
    return getattr(settings, lower, None) or getattr(settings, UPPER, default)


# -------------------------------
# Session helpers
# -------------------------------
SID_COOKIE_NAME = os.getenv("SID_COOKIE_NAME", "sid")
SESSION_TTL_SECONDS = int(os.getenv("SESSION_TTL_SECONDS", "3600"))
ACCESS_TOKEN_REFRESH_SKEW_SECONDS = int(os.getenv("ACCESS_TOKEN_REFRESH_SKEW_SECONDS", "60"))

async def _session_set_many(store: RedisSession, sid: str, mapping: dict, ttl: int | None = None) -> None:
    """
    Best-effort 'set_many' for our session dicts.
    If the store exposes set_many, use it. Otherwise: get -> update -> set.
    """
    try:
        set_many = getattr(store, "set_many", None)
        if set_many and callable(set_many):
            if _pyinspect.iscoroutinefunction(set_many):
                await set_many(mapping, prefix=SESSION_PREFIX, ttl=ttl)
            else:
                set_many(mapping, prefix=SESSION_PREFIX, ttl=ttl)
            return
    except Exception:
        # fall back below
        pass

    # Fallback: merge and set the whole session
    try:
        get_fn = getattr(store, "get", None)
        if _pyinspect.iscoroutinefunction(get_fn):
            current = await store.get(sid) or {}
        else:
            current = store.get(sid) or {}
    except Exception:
        current = {}

    current = dict(current)
    current.update(mapping)

    set_fn = getattr(store, "set", None)
    if _pyinspect.iscoroutinefunction(set_fn):
        await store.set(sid, current, ttl=ttl)
    else:
        store.set(sid, current, ttl=ttl)


async def record_tokens_to_session(store: RedisSession, sid: str, tok: dict, user_email: str | None = None) -> None:
    now = int(time.time())
    mapping = {
        "access_token": tok.get("access_token"),
        "refresh_token": tok.get("refresh_token"),
        "expires_at": now + int(tok.get("expires_in", 300)),
        "refresh_expires_at": (now + int(tok["refresh_expires_in"])) if tok.get("refresh_expires_in") else None,
    }
    if user_email:
        mapping["email"] = user_email
    await _session_set_many(store, sid, mapping, ttl=SESSION_TTL_SECONDS)

# -------- Verbose OIDC tracing (optional, guarded by OSSS_VERBOSE_AUTH=1) --------
def _mask(s: Optional[str], show: int = 2) -> Optional[str]:
    if not s:
        return s
    return s[:show] + "…" if len(s) > show else "…"

def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    v = os.getenv(name, default)
    return v if v and str(v).strip() != "" else default

async def _probe_oidc_discovery_and_jwks(issuer: str, explicit_jwks: Optional[str] = None) -> None:
    """
    Best-effort probe: fetch discovery doc + JWKS and log a concise summary.
    Never fails the app; purely diagnostic.
    """
    log = logging.getLogger("OSSS.auth")
    disc_url = urljoin(issuer.rstrip("/") + "/", ".well-known/openid-configuration")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            d = await client.get(disc_url)
            log.debug("OIDC discovery GET %s -> %s", disc_url, d.status_code)
            if d.status_code == 200:
                disc = d.json()
                jwks_uri = explicit_jwks or disc.get("jwks_uri")
                token_endpoint = disc.get("token_endpoint")
                auth_endpoint = disc.get("authorization_endpoint")
                log.debug("OIDC discovery summary: issuer=%s token_endpoint=%s auth_endpoint=%s jwks_uri=%s",
                          disc.get("issuer"), token_endpoint, auth_endpoint, jwks_uri)
                if jwks_uri:
                    j = await client.get(jwks_uri)
                    log.debug("JWKS GET %s -> %s", jwks_uri, j.status_code)
                    if j.status_code == 200:
                        keys = j.json().get("keys", [])
                        kids = [k.get("kid") for k in keys if isinstance(k, dict)]
                        algs = list({k.get("alg") for k in keys if isinstance(k, dict) and k.get("alg")})
                        log.debug("JWKS summary: %d keys kids=%s algs=%s", len(keys), kids, algs)
            else:
                log.warning("OIDC discovery failed: %s %s", d.status_code, d.text[:400])
    except Exception as e:
        log.warning("OIDC discovery/JWKS probe error: %s", e)

def _enable_verbose_oidc_logging() -> None:
    """
    Crank up loggers commonly involved in OIDC and HTTP so we can see
    token exchange, discovery, JWKS fetch, and validation details.
    """
    targets = [
        "OSSS", "OSSS.auth", "OSSS.security", "main", "startup",
        "fastapi", "starlette", "uvicorn", "uvicorn.error", "uvicorn.access",
        "authlib", "oauthlib", "jose", "jwcrypto",
        "httpx", "urllib3", "requests",
    ]
    for name in targets:
        logging.getLogger(name).setLevel(logging.DEBUG)
    # ensure uvicorn respects debug if launched without --log-level
    os.environ.setdefault("UVICORN_LOG_LEVEL", "debug")
    os.environ.setdefault("PYTHONLOGLEVEL", "DEBUG")
    logging.getLogger("OSSS.auth").debug("Verbose OIDC logging enabled.")

def create_app() -> FastAPI:
    # define a lifespan handler
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """
        Handles startup/shutdown tasks for the app (runs once on start, once on stop).
        """
        # ---------------- STARTUP ----------------

        # DB engine/sessionmaker bound to THIS loop
        app.state.db_engine = create_async_engine(
            settings.DATABASE_URL,
            pool_pre_ping=True,
        )
        app.state.async_sessionmaker = async_sessionmaker(
            app.state.db_engine, expire_on_commit=False, class_=AsyncSession
        )
        # Ensure all deps that call get_sessionmaker() use the app-scoped one
        def _sessionmaker_override():
            return app.state.async_sessionmaker
        app.dependency_overrides[get_sessionmaker] = _sessionmaker_override

        # Create probe router
        probe = APIRouter()

        @probe.get("/_oauth_probe", tags=["_debug"])
        async def _oauth_probe(
            _token: str = Depends(ensure_access_token),
            user: dict | None = Depends(get_current_user),
        ):
            return {"ok": True, "sub": (user or {}).get("sub")}


        @app.get("/_session_ttl", tags=["_debug"])
        async def session_ttl(key: str, store: RedisSession = Depends(get_session_store)):
            return await probe_key_ttl(store, key)

        @app.get("/_session_keys", tags=["_debug"])
        async def session_keys(limit: int = 20, store: RedisSession = Depends(get_session_store)):
            patt = f"{SESSION_PREFIX}*"
            keys = []
            async for k in store._r.scan_iter(match=patt, count=limit):  # type: ignore[attr-defined]
                keys.append(k.removeprefix(SESSION_PREFIX))
                if len(keys) >= limit:
                    break
            return {"keys": keys}

        @app.exception_handler(IntegrityError)
        async def integrity_error_handler(request: Request, exc: IntegrityError):
            """
            Map DB integrity errors to clear 4xx responses instead of 500.
            - Unique constraint -> 409 Conflict
            - Not-null / FK / Check -> 422 Unprocessable Entity (validation-like)
            - Otherwise -> 400 Bad Request
            """
            orig = getattr(exc, "orig", None)
            message = str(orig or exc)

            status_code = 400
            detail = "Integrity error"

            # asyncpg-specific (PostgreSQL) precise mapping
            if _HAS_ASYNCPG and orig is not None:
                if isinstance(orig, UniqueViolationError):
                    status_code = 409
                    detail = "Unique constraint violation"
                elif isinstance(orig, ForeignKeyViolationError):
                    status_code = 422
                    detail = "Foreign key constraint failed"
                elif isinstance(orig, NotNullViolationError):
                    status_code = 422
                    detail = "Missing required field (NOT NULL violation)"
                elif isinstance(orig, CheckViolationError):
                    status_code = 422
                    detail = "Check constraint failed"
            else:
                # Generic string heuristics (works across DBs/drivers)
                low = message.lower()
                if "unique constraint" in low or "duplicate key" in low:
                    status_code = 409
                    detail = "Unique constraint violation"
                elif "foreign key" in low:
                    status_code = 422
                    detail = "Foreign key constraint failed"
                elif "not null" in low or "null value in column" in low:
                    status_code = 422
                    detail = "Missing required field (NOT NULL violation)"
                elif "check constraint" in low:
                    status_code = 422
                    detail = "Check constraint failed"

            # Log once with context; don't leak sensitive values
            log.exception(
                "IntegrityError on %s %s -> %s: %s",
                request.method, request.url.path, status_code, message
            )

            return JSONResponse(
                status_code=status_code,
                content={
                    "detail": {
                        "error": "integrity_error",
                        "reason": detail,
                        "db_message": message,
                    }
                },
            )

        app.include_router(probe)
        app.include_router(sessions_diag_router)
        app.include_router(logout_router)

        @app.get("/whoami", tags=["debug"])
        async def whoami(consul: Consul = Depends(consul_client)):
            host, port = pick_healthy_service(consul, "users-api")
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(f"http://{host}:{port}/me")
                r.raise_for_status()
                return r.json()

        # DB ping (unless testing) using the app-scoped sessionmaker
        if not settings.TESTING:
            try:
                async_session = app.state.async_sessionmaker
                async with async_session() as session:
                    await session.execute(sa.text("SELECT 1"))
            except Exception:
                pass

                # --- optional app-level OIDC tracing ---
                if os.getenv("OSSS_VERBOSE_AUTH", "0") == "1":
                    _enable_verbose_oidc_logging()
                    issuer = _env("OIDC_ISSUER", "http://localhost:8080/realms/OSSS")
                    jwks = _env("OIDC_JWKS_URL")
                    client_id = _env("OIDC_CLIENT_ID", "osss-api")
                    client_secret = _env("OIDC_CLIENT_SECRET")
                    logging.getLogger("OSSS.auth").debug(
                        "OIDC config: issuer=%s client_id=%s jwks=%s client_secret=%s",
                        issuer, client_id, jwks, _mask(client_secret)
                    )
                    # fire and forget: discovery + JWKS summary
                    await _probe_oidc_discovery_and_jwks(issuer, explicit_jwks=jwks)

        # Swagger OAuth init
        oauth_cfg = {
            "clientId": settings.SWAGGER_CLIENT_ID,
            "usePkceWithAuthorizationCodeGrant": settings.SWAGGER_USE_PKCE,
            "scopes": "openid profile email",
            **({"clientSecret": settings.SWAGGER_CLIENT_SECRET} if settings.SWAGGER_CLIENT_SECRET else {}),
        }
        app.swagger_ui_init_oauth = oauth_cfg

        if os.getenv("OSSS_DEBUG_MAPPINGS") == "1":
            _dump_mappings("[mappings][startup]")

        print(
            "[startup] mounted routes:",
            sorted([r.path for r in app.routes if isinstance(r, APIRoute)])
        )

        # -------- Consul registration (non-blocking) --------
        app.state.consul = None
        #if os.getenv("CONSUL_ENABLE", "1") not in ("0", "false", "False"):
        if (1):
            try:
                c = Consul(host=CONSUL_HOST, port=CONSUL_PORT)

                # If your health router exposes a different path, change here.
                health_path = "/healthz"

                c.agent.service.register(
                    name=SERVICE_NAME,
                    service_id=SERVICE_ID,
                    address=APP_HOST,  # what peers use to reach THIS instance
                    port=int(APP_PORT),
                    tags=["fastapi", "osss", "v1"],
                    check={
                        "http": f"http://{APP_HOST}:{APP_PORT}{health_path}",
                        "interval": "10s",
                        "timeout": "2s",
                        "DeregisterCriticalServiceAfter": "1m",
                    },
                )
                app.state.consul = c
                logging.getLogger("startup").info(
                    "[consul] registered %s at %s:%s", SERVICE_ID, APP_HOST, APP_PORT
                )
            except Exception as e:
                logging.getLogger("startup").warning(
                    "[consul] registration skipped: %s", e
                )

        # hand control to application
        yield

        # -------- Consul deregistration --------
        try:
            c = getattr(app.state, "consul", None)
            if c is not None:
                c.agent.service.deregister(SERVICE_ID)
                logging.getLogger("startup").info("[consul] deregistered %s", SERVICE_ID)
        except Exception as e:
            logging.getLogger("startup").warning("[consul] deregister failed: %s", e)

        # ---------------- SHUTDOWN ----------------
        # Close DB engine BEFORE loop closes (prevents asyncpg 'loop is closed')
        try:
            await app.state.db_engine.dispose()
        except Exception:
            pass

        # Close session store (and its Redis client) on THIS loop
        try:
            store = getattr(app.state, "session_store", None)
            if store is not None:
                if hasattr(store, "aclose") and _pyinspect.iscoroutinefunction(store.aclose):
                    await store.aclose()  # type: ignore[func-returns-value]
                else:
                    r = getattr(store, "_r", None)
                    if r is not None and hasattr(r, "aclose"):
                        await r.aclose()  # type: ignore[func-returns-value]
        except Exception:
            pass

    # instantiate FastAPI with the lifespan handler
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        generate_unique_id_function=generate_unique_id,
        lifespan=lifespan,
    )

    attach_session_store(app)  # adds startup/shutdown hooks + app.state.session_store

    # Sessions
    secret_key = _cfg("session_secret", "SESSION_SECRET", "dev-insecure-change-me")
    cookie_name = _cfg("session_cookie_name", "SESSION_COOKIE_NAME", "osss_session")
    max_age = _cfg("session_max_age", "SESSION_MAX_AGE", 60 * 60 * 24 * 14)
    https_only = _cfg("session_https_only", "SESSION_HTTPS_ONLY", False)
    same_site = _cfg("session_samesite", "SESSION_SAMESITE", "lax")

    app.add_middleware(
        SessionMiddleware,
        secret_key=secret_key,
        max_age=max_age,
        session_cookie=cookie_name,
        same_site=same_site,
        https_only=https_only,
    )

    app.add_middleware(SessionTTL)  # <- after your session-loader middleware

    # Base / utility routers
    app.include_router(debug.router)
    app.include_router(health_router)
    app.include_router(me_router)  # mounts at /me

    # Auth routers
    app.include_router(auth_router, prefix="/auth", tags=["auth"])
    #app.include_router(auth_proxy.router, prefix="/auth/proxy", tags=["auth"])

    # Dynamic model routers under /api
    existing: set[tuple[str, tuple[str, ...]]] = {
        (r.path, tuple(sorted((r.methods or [])))) for r in app.routes if isinstance(r, APIRoute)
    }
    mounted_models: set[str] = set()

    for name, router in generate_routers_for_all_models(prefix_base="/api"):
        if name in mounted_models:
            log.warning("[startup] skipping %s (already mounted by name)", name)
            continue

        sig = _routes_signature(router)
        if any(k in existing for k in sig):
            log.warning("[startup] skipping %s (route collision detected)", name)
            continue

        app.include_router(router)
        existing.update(sig)
        mounted_models.add(name)
        log.info("[startup] mounted dynamic router: %s", name)

    # -----------------------------
    # Middleware: proactive refresh
    # -----------------------------
    @app.middleware("http")
    async def proactive_refresh(request: Request, call_next):
        """
        If the access token is close to expiration (within skew), refresh it using the
        refresh token and store the new values back into the server-side session.
        """
        response = None
        try:
            store = getattr(request.app.state, "session_store", None)
            if store:
                sid = request.cookies.get(SID_COOKIE_NAME)
                if sid:
                    # Load current session
                    try:
                        sess = await store.get(sid)  # type: ignore[attr-defined]
                    except TypeError:
                        sess = store.get(sid)  # sync fallback
                    if isinstance(sess, dict):
                        now = int(time.time())
                        exp = sess.get("expires_at")
                        rt = sess.get("refresh_token")
                        if exp and rt and (exp - now) <= ACCESS_TOKEN_REFRESH_SKEW_SECONDS:
                            try:
                                new = await refresh_access_token(rt)
                                mapping = {
                                    "access_token": new.get("access_token"),
                                    "refresh_token": new.get("refresh_token", rt),
                                    "expires_at": now + int(new.get("expires_in", 300)),
                                }
                                r_exp = new.get("refresh_expires_in")
                                if r_exp:
                                    mapping["refresh_expires_at"] = now + int(r_exp)
                                await _session_set_many(store, sid, mapping, ttl=SESSION_TTL_SECONDS)
                                log.debug("[session] proactively refreshed token for sid=%s…", sid[:8])
                            except Exception as e:
                                log.warning("proactive refresh failed: %s", e)
        finally:
            response = await call_next(request)
        return response

    # -----------------------------
    # Middleware: ensure SID cookie
    # -----------------------------
    @app.middleware("http")
    async def session_tracker(request: Request, call_next):
        response = await call_next(request)  # process first to avoid masking errors
        try:
            sid = await ensure_sid_cookie_and_store(request, response)
            request.state.sid = sid
            log.debug("Request %s %s -> sid=%s…", request.method, request.url.path, sid[:8])
        except Exception as e:
            log.exception("Failed to ensure sid: %s", e)
        return response

    return app


app = create_app()

from fastapi.openapi.utils import get_openapi

def _strip_http_bearer_from_openapi(app: FastAPI):
    def _custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema
        schema = get_openapi(
            title=app.title,
            version=app.version,
            routes=app.routes,
            description=getattr(app, "description", None),
        )
        comps = schema.get("components", {}).get("securitySchemes", {})
        to_remove = [k for k, v in comps.items()
                     if isinstance(v, dict) and v.get("type") == "http" and v.get("scheme") == "bearer"]
        if to_remove:
            for k in to_remove:
                comps.pop(k, None)
            if "security" in schema and isinstance(schema["security"], list):
                schema["security"] = [
                    s for s in schema["security"]
                    if not any(k in s for k in to_remove)
                ]
            for _, methods in (schema.get("paths") or {}).items():
                for _, op in methods.items():
                    if isinstance(op, dict) and "security" in op and isinstance(op["security"], list):
                        op["security"] = [
                            s for s in op["security"]
                            if not any(k in s for k in to_remove)
                        ]
        app.openapi_schema = schema
        return app.openapi_schema
    app.openapi = _custom_openapi

# call it after app creation
_strip_http_bearer_from_openapi(app)
