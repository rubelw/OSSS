# src/OSSS/main.py
from __future__ import annotations

import logging
import sqlalchemy as sa
from fastapi import FastAPI, APIRouter, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute
from starlette.middleware.sessions import SessionMiddleware
from OSSS.settings import settings


from OSSS.core.config import settings
from OSSS.db import get_sessionmaker

from OSSS.api.generated_resources.register_all import generate_routers_for_all_models
from OSSS.api.routers.auth_flow import router as auth_router  # single source of /auth/token
from OSSS.api import debug
from OSSS.api import auth_proxy  # keep but under non-conflicting prefix
from OSSS.api.routers.me import router as me_router

from OSSS.auth.deps import oauth2  # used in _oauth_probe

log = logging.getLogger("startup")


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
    # safe: no eager evaluation
    return getattr(settings, lower, None) or getattr(settings, UPPER, default)

def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        generate_unique_id_function=generate_unique_id,
    )

    # when configuring your session middleware / auth:
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

    # Auth: avoid /auth/token duplication.
    # If you still need the proxy endpoints, keep them under a distinct prefix.
    app.include_router(auth_router, prefix="/auth", tags=["auth"])
    app.include_router(auth_proxy.router, prefix="/auth/proxy", tags=["auth"])  # no collision now

    # Dynamic model routers (dedupe on path+method to avoid double mounting)
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

    # Startup hooks
    @app.on_event("startup")
    async def _startup() -> None:
        # tiny probe so Swagger "Authorize" shows usable OAuth2 flow
        probe = APIRouter()

        @probe.get("/_oauth_probe", tags=["_debug"])
        async def _oauth_probe(_token: str = Security(oauth2)):
            return {"ok": True}

        app.include_router(probe)

        # DB ping (dev friendly)
        if not settings.TESTING:
            try:
                async_session = get_sessionmaker()
                async with async_session() as session:
                    await session.execute(sa.text("SELECT 1"))
            except Exception:
                pass  # don't crash app in dev

        # Swagger OAuth init
        oauth_cfg = {
            "clientId": settings.SWAGGER_CLIENT_ID,
            "usePkceWithAuthorizationCodeGrant": settings.SWAGGER_USE_PKCE,
            "scopes": "openid profile email",
            **({"clientSecret": settings.SWAGGER_CLIENT_SECRET} if settings.SWAGGER_CLIENT_SECRET else {}),

        }
        if settings.SWAGGER_CLIENT_SECRET:
            oauth_cfg["clientSecret"] = settings.SWAGGER_CLIENT_SECRET  # dev only
        app.swagger_ui_init_oauth = oauth_cfg

        # Log mounted routes (handy for confirming no dupes)
        print(
            "[startup] mounted routes:",
            sorted([r.path for r in app.routes if isinstance(r, APIRoute)]),
        )

    return app


app = create_app()
