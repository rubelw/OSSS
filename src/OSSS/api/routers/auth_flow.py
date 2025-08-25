# src/OSSS/api/routers/auth_flow.py
from __future__ import annotations

import os
import requests
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.security import OAuth2PasswordBearer

# This path must match how you mount the router (see next step).
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/auth/token",
    scopes={"openid": "OpenID Connect", "profile": "User profile", "email": "Email"},
)

router = APIRouter(tags=["auth"])

KEYCLOAK_BASE_URL = os.getenv("KEYCLOAK_BASE_URL", "http://localhost:8085").rstrip("/")
KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM", "OSSS")
KEYCLOAK_CLIENT_ID = os.getenv("KEYCLOAK_CLIENT_ID", "osss-api")          # confidential API client
KEYCLOAK_CLIENT_SECRET = os.getenv("KEYCLOAK_CLIENT_SECRET", "changeme")  # its secret

TOKEN_URL = f"{KEYCLOAK_BASE_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/token"


@router.post("/token")
def password_grant_token(form: OAuth2PasswordRequestForm = Depends()):
    """
    Accept x-www-form-urlencoded fields:
      - username
      - password
      - (optional) scope, grant_type, client_id/client_secret
    Proxies to Keycloak token endpoint and returns its JSON.
    """
    data = {
        "grant_type": "password",
        "client_id": KEYCLOAK_CLIENT_ID,
        "client_secret": KEYCLOAK_CLIENT_SECRET,
        "username": form.username,
        "password": form.password,
        # FastAPI's OAuth2PasswordRequestForm gives scope as a space-separated string
        "scope": form.scopes and " ".join(form.scopes) or "openid profile email",
    }

    try:
        resp = requests.post(TOKEN_URL, data=data, timeout=10)
    except requests.RequestException:
        raise HTTPException(status_code=502, detail="Keycloak token endpoint unavailable")

    if resp.status_code != 200:
        # tests expect 401 on “bad credentials”
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=resp.text)

    return resp.json()
