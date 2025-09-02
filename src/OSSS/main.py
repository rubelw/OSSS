# src/OSSS/main.py
from __future__ import annotations

import logging, logging.config
import sqlalchemy as sa
from fastapi import FastAPI, APIRouter, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute
from starlette.middleware.sessions import SessionMiddleware
from OSSS.settings import settings
import os
from sqlalchemy.orm import class_mapper
from sqlalchemy.orm.exc import UnmappedClassError
from sqlalchemy.inspection import inspect as sa_inspect

from OSSS.core.config import settings
from OSSS.db import get_sessionmaker

from OSSS.api.generated_resources.register_all import generate_routers_for_all_models
from OSSS.api.routers.auth_flow import router as auth_router  # single source of /auth/token
from OSSS.api import debug
from OSSS.api import auth_proxy  # keep but under non-conflicting prefix
from OSSS.api.routers.me import router as me_router
from OSSS.api.routers.health import router as health_router
from contextlib import asynccontextmanager

from OSSS.auth.deps import oauth2  # used in _oauth_probe

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
        "uvicorn":         {"handlers": ["console"], "level": "INFO"},
        "uvicorn.error":   {"handlers": ["console"], "level": "INFO", "propagate": False},
        "uvicorn.access":  {"handlers": ["console"], "level": "INFO", "propagate": False},
        "startup":         {"handlers": ["console"], "level": "DEBUG", "propagate": False},
        "OSSS":            {"handlers": ["console"], "level": "DEBUG", "propagate": False},
    },
}

logging.config.dictConfig(LOGGING)
log = logging.getLogger("startup")


def _discover_Base():
    """Best-effort discovery of the SQLAlchemy Declarative Base."""
    candidates = [
        "OSSS.db.base:Base",
        "OSSS.db.models.base:Base",
        "OSSS.db.models:Base",
    ]
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
    return None, locals().get("last_err", "No suitable Base found")


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
    # Optional sanity check for ApVendor
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


# Make operation IDs unique across all routers
def generate_unique_id(route: APIRoute) -> str:
    methods = "_".join(sorted((route.methods or []), key=str.lower)).lower()
    path = route.path_format.replace("/", "_").replace("{", "").replace("}", "").strip("_")
    tag = (route.tags[0] if route.tags else "default").lower().replace(" ", "_")
    return f"{tag}__{methods}__{path}"


def _routes_signature(router: APIRouter) -> set[tuple[str, tuple[str, ...]]]:
    """(path, methods) signature for a router (used to detect collisions)."""
    sig: set[tuple[str, tuple[str, ...]]] = set()
    for r in router.routes:
        if isinstance(r, APIRoute):
            methods = tuple(sorted((r.methods or [])))
            sig.add((r.path, methods))
    return sig


def _cfg(lower: str, UPPER: str, default=None):
    return getattr(settings, lower, None) or getattr(settings, UPPER, default)


def create_app() -> FastAPI:
    # ---------- lifespan replaces on_event ----------
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Startup
        probe = APIRouter()
        @probe.get("/_oauth_probe", tags=["_debug"])
        async def _oauth_probe(_token: str = Security(oauth2)):
            return {"ok": True}
        app.include_router(probe)

        # DB ping (skip in tests)
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
        if settings.SWAGGER_CLIENT_SECRET:
            oauth_cfg["clientSecret"] = settings.SWAGGER_CLIENT_SECRET
        app.swagger_ui_init_oauth = oauth_cfg

        print(
            "[startup] mounted routes:",
            sorted([r.path for r in app.routes if isinstance(r, APIRoute)]),
        )

        if os.getenv("OSSS_DEBUG_MAPPINGS") == "1":
            _dump_mappings("[mappings][startup]")

        try:
            yield  # ---- application runs here ----
        finally:
            # Shutdown (add cleanup if needed)
            pass
    # -----------------------------------------------

    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        generate_unique_id_function=generate_unique_id,
        lifespan=lifespan,  # ✅ use lifespan
    )

    # Mount health endpoints (place BEFORE any auth-guarded routers if you apply global dependencies)
    app.include_router(health_router)

    # Session middleware
    secret_key = _cfg("session_secret", "SESSION_SECRET", "dev-insecure-change-me")
    cookie_name = _cfg("session_cookie_name", "SESSION_COOKIE_NAME", "osss_session")
    max_age = _cfg("session_max_age", "SESSION_MAX_AGE", 60 * 60 * 24 * 14)
    https_only = _cfg("session_https_only", "SESSION_HTTPS_ONLY", False)
    same_site = _cfg("session_samesite", "SESSION_SAMESITE", "lax")

    app.add_middleware(
        SessionMiddleware,
        secret_key=secret_key,
        session_cookie=cookie_name,
        max_age=max_age,
        https_only=https_only,
        same_site=same_site,
    )

    # Base/utility routers
    app.include_router(debug.router)
    app.include_router(me_router)

    # Auth routers
    app.include_router(auth_router, prefix="/auth", tags=["auth"])
    app.include_router(auth_proxy.router, prefix="/auth/proxy", tags=["auth"])

    # Dynamic model routers
    existing: set[tuple[str, tuple[str, ...]]] = {
        (r.path, tuple(sorted((r.methods or [])))) for r in app.routes if isinstance(r, APIRoute)
    }
    mounted_models: set[str] = set()

    for name, router in generate_routers_for_all_models(prefix_base="/api"):
        log.info(" routers name: %s %s", name, router)

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

    # 🔥 Removed deprecated @app.on_event("startup") block

    return app


app = create_app()
