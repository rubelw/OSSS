# src/OSSS/main.py
from __future__ import annotations

import sqlalchemy as sa
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from OSSS.core.config import settings
from OSSS.db import get_sessionmaker

# Router imports (each file should define `router = APIRouter(...)`)
from OSSS.api.routers.health import router as health_router
from OSSS.api.routers.me import router as me_router
from OSSS.api.routers.admin_settings_states import router as states_router
from OSSS.api.routers.admin_settings_schools import router as schools_router
from OSSS.api.routers.admin_settings_districts import router as districts_router
from OSSS.api.routers.sis_settings_academic_terms import router as sis_academic_terms_router
from OSSS.api.routers.sis_settings_standardized_tests import router as sis_standardized_tests_router
from OSSS.api.routers.sis_settings_attendance_codes import router as sis_attendance_codes_router

from OSSS.api.routers.sis_settings_behavior_codes import router as sis_behavior_codes_router
from OSSS.api.routers import activities as activities_router


from OSSS.api.routers.auth_flow import router as auth_router


def create_app() -> FastAPI:
    app = FastAPI(title=settings.APP_NAME, version=settings.APP_VERSION)

    # --- CORS ---
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.CORS_ORIGINS),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- Routers ---
    app.include_router(health_router)
    app.include_router(me_router)
    app.include_router(states_router)
    app.include_router(schools_router)
    app.include_router(districts_router)
    app.include_router(sis_behavior_codes_router)
    app.include_router(sis_academic_terms_router)
    app.include_router(sis_standardized_tests_router)
    app.include_router(sis_attendance_codes_router)


    app.include_router(activities_router.router)

    app.include_router(auth_router)

    # --- Startup (DB ping + Swagger OAuth) ---
    @app.on_event("startup")
    async def _startup() -> None:
        # DB ping unless in tests
        if not settings.TESTING:
            try:
                async_session = get_sessionmaker()
                async with async_session() as session:
                    await session.execute(sa.text("SELECT 1"))
            except Exception:
                # Don't crash the app at import-time in dev; log if you have logging configured
                pass

        # Swagger "Authorize" (PKCE for public client)
        oauth_cfg = {
            "clientId": settings.SWAGGER_CLIENT_ID,
            "usePkceWithAuthorizationCodeGrant": settings.SWAGGER_USE_PKCE,
            "scopes": "openid profile email",
        }
        if settings.SWAGGER_CLIENT_SECRET:
            oauth_cfg["clientSecret"] = settings.SWAGGER_CLIENT_SECRET  # dev only
        app.swagger_ui_init_oauth = oauth_cfg

    return app


app = create_app()
