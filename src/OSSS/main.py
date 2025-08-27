# src/OSSS/main.py
from __future__ import annotations

import logging
import sqlalchemy as sa
from fastapi import FastAPI, APIRouter, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute

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


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        generate_unique_id_function=generate_unique_id,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.CORS_ORIGINS),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
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
