# src/OSSS/main.py
from __future__ import annotations

import os
import requests
import sqlalchemy as sa
from fastapi import FastAPI, Depends, HTTPException, Security, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from OSSS.db import get_sessionmaker
from OSSS.auth import require_auth
from OSSS.routes.states import router as states_router

# ---------- App ----------
app = FastAPI(title="OSSS API", version="0.1.0")

# CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("NEXT_PUBLIC_PUBLIC_URL", "http://localhost:3000")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- OAuth2 (for docs "Authorize" button) ----------
# IMPORTANT: tokenUrl must match the path we expose below (@app.post("/token"))
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token")

# ---------- Health ----------
@app.get("/healthz", include_in_schema=False)
def healthz():
    return {"status": "ok"}

# ---------- Startup: DB ping + Swagger OAuth ----------
@app.on_event("startup")
async def startup() -> None:
    # DB ping
    async_session = get_sessionmaker()
    async with async_session() as session:  # type: AsyncSession
        await session.execute(sa.text("SELECT 1"))

    # Swagger UI OAuth (browser flow via public client using PKCE)
    app.swagger_ui_init_oauth = {
        "clientId": os.getenv("SWAGGER_CLIENT_ID", "osss-web"),  # public web client
        "clientSecret": os.getenv("SWAGGER_CLIENT_SECRET","password"),
        "usePkceWithAuthorizationCodeGrant": True,
        "scopes": "openid profile email",
    }

# ---------- Keycloak config ----------
KEYCLOAK_BASE_URL = os.getenv("KEYCLOAK_BASE_URL", "http://localhost:8085").rstrip("/")
KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM", "OSSS")

# Confidential backend client (password grant + introspection)
KEYCLOAK_CLIENT_ID = os.getenv("KEYCLOAK_CLIENT_ID", "osss-api")
KEYCLOAK_CLIENT_SECRET = os.getenv("KEYCLOAK_CLIENT_SECRET", "")

CALLBACK_URL = os.getenv("CALLBACK_URL", "http://localhost:8081/callback")

TOKEN_URL = f"{KEYCLOAK_BASE_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/token"
AUTH_URL = f"{KEYCLOAK_BASE_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/auth"

# ---------- Auth endpoints ----------

# 1) Password grant for Swagger ("Authorize" → password) and scripts
@app.post("/token", tags=["auth"])
def password_grant_token(form: OAuth2PasswordRequestForm = Depends()):
    if not KEYCLOAK_CLIENT_SECRET:
        # Make it obvious in dev if secret isn't set
        raise HTTPException(status_code=500, detail="KEYCLOAK_CLIENT_SECRET not set")

    data = {
        "grant_type": "password",
        "client_id": KEYCLOAK_CLIENT_ID,
        "client_secret": KEYCLOAK_CLIENT_SECRET,
        "username": form.username,
        "password": form.password,
        "scope": " ".join(form.scopes) if form.scopes else "openid profile email",
    }
    try:
        r = requests.post(TOKEN_URL, data=data, timeout=10)
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Keycloak token endpoint unreachable: {e}") from e

    if r.status_code != 200:
        # surface Keycloak’s message so you can see exactly why
        raise HTTPException(status_code=401, detail=r.text)
    return r.json()

# 2) Echo current claims (protected)
@app.get("/me", tags=["auth"])
def me(
    _bearer: str = Security(oauth2_scheme),   # shows the Authorize UI in docs
    claims: dict = Depends(require_auth),     # your introspection-based check
):
    return {
        "sub": claims.get("sub"),
        "preferred_username": claims.get("preferred_username"),
        "email": claims.get("email"),
        "roles": (claims.get("realm_access") or {}).get("roles", []),
        "aud": claims.get("aud"),
        "azp": claims.get("azp"),
        "iss": claims.get("iss"),
    }

# 3) Browser login helper (public client via PKCE) and callback (confidential client)
@app.get("/login-link", include_in_schema=False)
def login_link() -> str:
    from urllib.parse import urlencode
    params = {
        "scope": "openid profile email",
        "response_type": "code",
        "client_id": os.getenv("SWAGGER_CLIENT_ID", "osss-web"),  # public client
        "redirect_uri": CALLBACK_URL,
    }
    return f"{AUTH_URL}?{urlencode(params)}"

@app.get("/callback", include_in_schema=False)
def callback(code: str):
    if not KEYCLOAK_CLIENT_SECRET:
        raise HTTPException(status_code=500, detail="KEYCLOAK_CLIENT_SECRET not set")
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "client_id": KEYCLOAK_CLIENT_ID,
        "client_secret": KEYCLOAK_CLIENT_SECRET,
        "redirect_uri": CALLBACK_URL,
    }
    r = requests.post(TOKEN_URL, data=data, timeout=10)
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail=f"Token exchange failed: {r.text}")
    tokens = r.json()

    # Dev/demo redirect back to Next with tokens in the fragment
    from urllib.parse import urlencode
    web_target = os.getenv("WEB_CALLBACK", "http://localhost:3000/auth/callback")
    frag = urlencode(
        {
            "access_token": tokens.get("access_token", ""),
            "refresh_token": tokens.get("refresh_token", ""),
            "token_type": tokens.get("token_type", ""),
            "expires_in": tokens.get("expires_in", ""),
        }
    )
    return RedirectResponse(f"{web_target}#{frag}", status_code=302)

# ---------- Feature routers (protected) ----------
# Your states router already enforces auth via require_auth + Security(oauth2_scheme)
app.include_router(states_router)
