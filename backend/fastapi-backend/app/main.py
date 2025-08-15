from __future__ import annotations

from fastapi import FastAPI
from fastapi.security import HTTPBearer, OAuth2AuthorizationCodeBearer
from fastapi.openapi.utils import get_openapi
from fastapi.routing import APIRoute
import logging
import sys
import sqlalchemy as sa
from datetime import datetime

from .settings import settings
from .routes import register_routes  # <-- all routes live here

from . import models  # imports all models
from sqlalchemy.orm import configure_mappers


app = FastAPI(title=settings.APP_NAME, version="1.0.0")

# import your async engine
from app.database import engine  # AsyncEngine

# One-time console logger setup
_console_logger = logging.getLogger("alembic.console")
if not _console_logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s"))
    _console_logger.addHandler(_handler)
_console_logger.setLevel(logging.INFO)
_console_logger.propagate = False

@app.on_event("startup")
async def _configure_sqlalchemy_mappers():
    configure_mappers()
    try:
        async with engine.begin() as conn:
            rows = (await conn.execute(sa.text("SELECT version_num FROM alembic_version"))).all()
        versions = [r[0] for r in rows]
        msg = "alembic_version rows: " + (", ".join(versions) if versions else "(none)")
    except Exception as e:
        msg = f"Could not read alembic_version: {e!r}"

        # log to console via logger and print (belt + suspenders)
    _console_logger.info(msg)
    print(f"{datetime.utcnow().isoformat()}Z INFO [alembic.console] {msg}", file=sys.stdout, flush=True)

    # 2) optional: show /schools data presence (count + sample)
    try:
        async with engine.begin() as conn:
            count = await conn.execute(sa.text("SELECT * FROM schools"))
            rows = (await conn.execute(sa.text("SELECT * FROM schools"))).all()
            data = [r[0] for r in rows]
            msg = "school data: " + (", ".join(data) if data else "(none)")

    except Exception as e:
        msg = f"Could not read schools data: {e!r}"

    _console_logger.info(msg)


# --- Keycloak / Swagger OAuth setup (docs-only objects live here) ---
KEYCLOAK_PUBLIC = (
    getattr(settings, "KEYCLOAK_PUBLIC_URL", None) or settings.KEYCLOAK_SERVER_URL
).rstrip("/")
realm = settings.KEYCLOAK_REALM

oauth2_scheme = OAuth2AuthorizationCodeBearer(
    authorizationUrl=f"{KEYCLOAK_PUBLIC}/realms/{realm}/protocol/openid-connect/auth",
    tokenUrl=f"{KEYCLOAK_PUBLIC}/realms/{realm}/protocol/openid-connect/token",
    scopes={"openid": "OpenID Connect", "profile": "Basic profile", "email": "Email"},
    scheme_name="KeycloakOAuth2",
)
bearer_scheme = HTTPBearer(scheme_name="BearerAuth")

app.swagger_ui_init_oauth = {
    "clientId": settings.KEYCLOAK_CLIENT_ID,
    "usePkceWithAuthorizationCodeGrant": True,
    "scopes": "openid profile email",
}

def custom_openapi():
    """
    Patch OpenAPI to declare KeycloakOAuth2 + Bearer and set a global
    'either/or' security requirement.
    """
    if app.openapi_schema:
        return app.openapi_schema

    schema = get_openapi(title=app.title, version="1.0.0", routes=app.routes)
    comps = schema.setdefault("components", {}).setdefault("securitySchemes", {})

    comps["KeycloakOAuth2"] = {
        "type": "oauth2",
        "flows": {
            "authorizationCode": {
                "authorizationUrl": f"{KEYCLOAK_PUBLIC}/realms/{realm}/protocol/openid-connect/auth",
                "tokenUrl": f"{KEYCLOAK_PUBLIC}/realms/{realm}/protocol/openid-connect/token",
                "scopes": {
                    "openid": "OpenID Connect",
                    "profile": "Basic profile",
                    "email": "Email",
                },
            }
        },
    }
    comps["BearerAuth"] = {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}

    # Global “either/or” security requirement
    schema["security"] = [{"KeycloakOAuth2": ["openid"]}, {"BearerAuth": []}]

    app.openapi_schema = schema
    return app.openapi_schema

app.openapi = custom_openapi

# --- Register all routes (moved to routes.py) ---
register_routes(app, oauth2_scheme)

# --- Optional: fail fast if operation_id duplicates slip in ---
_seen: dict[str, str] = {}
for r in app.routes:
    if isinstance(r, APIRoute):
        oid = r.operation_id or r.name
        if oid in _seen:
            raise RuntimeError(f"Duplicate operation_id '{oid}' for {r.path} and {_seen[oid]}")
        _seen[oid] = r.path
