# src/OSSS/main.py
from __future__ import annotations

import os
import logging
import logging.config
import sqlalchemy as sa

from contextlib import asynccontextmanager          # ADD THIS
from fastapi import FastAPI, APIRouter, Depends, Request
from fastapi.routing import APIRoute

from starlette.middleware.sessions import SessionMiddleware

from sqlalchemy.orm import class_mapper
from sqlalchemy.orm.exc import UnmappedClassError
from sqlalchemy.inspection import inspect as sa_inspect

from OSSS.core.config import settings
from OSSS.db import get_sessionmaker


from OSSS.api.generated_resources.register_all import generate_routers_for_all_models
from OSSS.api.routers.auth_flow import router as auth_router
from OSSS.api import debug
from OSSS.api import auth_proxy
from OSSS.api.routers.me import router as me_router
from OSSS.api.routers.health import router as health_router

# New auth deps (no oauth2 symbol anymore)
from OSSS.auth import ensure_access_token, get_current_user

from OSSS.sessions import attach_session_store, get_session_store, SESSION_PREFIX, ensure_sid_cookie_and_store, RedisSession, probe_key_ttl
from OSSS.sessions_diag import router as sessions_diag_router
from OSSS.app_logger import get_logger



LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "uvicorn": {
            "()": "uvicorn.logging.DefaultFormatter",
            "fmt": "%(levelprefix)s %(name)s: %(message)s",
            "use_colors": True,
        }
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "uvicorn"},
    },
    "loggers": {
        "uvicorn":        {"handlers": ["console"], "level": "INFO"},
        "uvicorn.error":  {"handlers": ["console"], "level": "INFO", "propagate": False},
        "uvicorn.access": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "startup":        {"handlers": ["console"], "level": "DEBUG", "propagate": False},
    },
}
logging.config.dictConfig(LOGGING)
log = logging.getLogger("main")



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
        log.info("  - %s (table=%s) PK=%s composite=%s cols=%s%s",
                 name, tablename, pks, composite_pk, cols, flag)

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


def create_app() -> FastAPI:
    # define a lifespan handler to replace deprecated on_event
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """
        Handles startup/shutdown tasks for the app.
        This runs once when the app starts and once when it stops.
        """
        # STARTUP logic
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
            # list raw redis keys; strip prefix for display
            patt = f"{SESSION_PREFIX}*"
            keys = []
            async for k in store._r.scan_iter(match=patt, count=limit):
                keys.append(k.removeprefix(SESSION_PREFIX))
                if len(keys) >= limit:
                    break
            return {"keys": keys}

        app.include_router(probe)
        app.include_router(sessions_diag_router)

        # DB ping (unless testing)
        if not settings.TESTING:
            try:
                async_session = get_sessionmaker()
                async with async_session() as session:
                    await session.execute(sa.text("SELECT 1"))
            except Exception:
                pass

        # Swagger OAuth init
        oauth_cfg = {
            "clientId": settings.SWAGGER_CLIENT_ID,
            "usePkceWithAuthorizationCodeGrant": settings.SWAGGER_USE_PKCE,
            "scopes": "openid profile email",
            **({"clientSecret": settings.SWAGGER_CLIENT_SECRET} if settings.SWAGGER_CLIENT_SECRET else {}),
        }
        app.swagger_ui_init_oauth = oauth_cfg

        # optional mapping dump
        if os.getenv("OSSS_DEBUG_MAPPINGS") == "1":
            _dump_mappings("[mappings][startup]")

        # print routes
        print("[startup] mounted routes:",
              sorted([r.path for r in app.routes if isinstance(r, APIRoute)]))

        # yield control to the application
        yield

        # SHUTDOWN logic (if you need any cleanup, put it here)

    # instantiate FastAPI with the lifespan handler
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        generate_unique_id_function=generate_unique_id,
        lifespan=lifespan,  # PASS lifespan handler here
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
        session_cookie="osss_session",
        same_site="lax",
        https_only=False,  # True in production behind HTTPS

    )

    # Base / utility routers
    app.include_router(debug.router)
    app.include_router(health_router)
    app.include_router(me_router)  # mounts at /me

    # Auth routers
    app.include_router(auth_router, prefix="/auth", tags=["auth"])
    app.include_router(auth_proxy.router, prefix="/auth/proxy", tags=["auth"])

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

    # Startup
    @app.on_event("startup")
    async def _startup() -> None:
        app.state.session_store = RedisSession()
        ok = await app.state.session_store.ping()
        if not ok:
            log.warning("Redis not reachable at startup.")

        # Small probe that enforces a token (no oauth2 symbol)
        probe = APIRouter()

        @probe.get("/_oauth_probe", tags=["_debug"])
        async def _oauth_probe(
            _token: str = Depends(ensure_access_token),
            user: dict | None = Depends(get_current_user),
        ):
            return {"ok": True, "sub": (user or {}).get("sub")}

        app.include_router(probe)

        # DB ping
        if not settings.TESTING:
            try:
                async_session = get_sessionmaker()
                async with async_session() as session:
                    await session.execute(sa.text("SELECT 1"))
            except Exception:
                pass

        # Swagger OAuth init
        oauth_cfg = {
            "clientId": settings.SWAGGER_CLIENT_ID,
            "usePkceWithAuthorizationCodeGrant": settings.SWAGGER_USE_PKCE,
            "scopes": "openid profile email",
            **({"clientSecret": settings.SWAGGER_CLIENT_SECRET} if settings.SWAGGER_CLIENT_SECRET else {}),
        }
        app.swagger_ui_init_oauth = oauth_cfg

        print(
            "[startup] mounted routes:",
            sorted([r.path for r in app.routes if isinstance(r, APIRoute)]),
        )

        if os.getenv("OSSS_DEBUG_MAPPINGS") == "1":
            _dump_mappings("[mappings][startup]")

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
        # find bearer-type schemes
        to_remove = [k for k, v in comps.items()
                     if isinstance(v, dict) and v.get("type") == "http" and v.get("scheme") == "bearer"]
        if to_remove:
            for k in to_remove:
                comps.pop(k, None)
            # remove global security refs to removed schemes
            if "security" in schema and isinstance(schema["security"], list):
                schema["security"] = [
                    s for s in schema["security"]
                    if not any(k in s for k in to_remove)
                ]
            # remove per-operation refs to removed schemes
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