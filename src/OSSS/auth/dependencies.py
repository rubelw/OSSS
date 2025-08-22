# src/OSSS/auth/dependencies.py
from __future__ import annotations

import os
from typing import Any, Dict, Optional, Iterable

import requests
from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer, OAuth2PasswordBearer
from fastapi.security.utils import get_authorization_scheme_param

# --------------------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------------------
KEYCLOAK_BASE_URL = os.getenv("KEYCLOAK_BASE_URL", "http://localhost:8085").rstrip("/")
KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM", "OSSS")

# Confidential client used to introspect tokens
INTROSPECT_CLIENT_ID = os.getenv("KEYCLOAK_CLIENT_ID", "osss-api")
INTROSPECT_CLIENT_SECRET = os.getenv("KEYCLOAK_CLIENT_SECRET", "changeme")

# Accept tokens for any of these audiences (aud) or authorized party (azp)
KEYCLOAK_ALLOWED_AUDIENCES: set[str] = {
    c.strip()
    for c in os.getenv("KEYCLOAK_ALLOWED_AUDIENCES", "osss-api,osss-web").split(",")
    if c.strip()
}

INTROSPECTION_URL = (
    f"{KEYCLOAK_BASE_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/token/introspect"
)

# Security helpers used by require_auth
http_bearer = HTTPBearer(auto_error=False)
oauth2_password = OAuth2PasswordBearer(tokenUrl="/token", auto_error=False)

# --------------------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------------------
def _aud_ok(aud: Any, azp: Optional[str]) -> bool:
    """
    Accept if token's `aud` contains any allowed audience OR `azp` matches.
    Keycloak may emit aud as str or list.
    """
    if isinstance(aud, str):
        if aud in KEYCLOAK_ALLOWED_AUDIENCES:
            return True
    elif isinstance(aud, Iterable):
        if any(a in KEYCLOAK_ALLOWED_AUDIENCES for a in aud):
            return True
    if azp and azp in KEYCLOAK_ALLOWED_AUDIENCES:
        return True
    return False


def _introspect(token: str) -> Dict[str, Any]:
    """
    Introspect a token via Keycloak.  Kept as a top-level symbol so tests can monkeypatch it.
    """
    data = {
        "token": token,
        "client_id": INTROSPECT_CLIENT_ID,
        "client_secret": INTROSPECT_CLIENT_SECRET,
    }
    try:
        r = requests.post(INTROSPECTION_URL, data=data, timeout=10)
    except requests.RequestException:
        raise HTTPException(status_code=502, detail="Keycloak introspection unavailable")

    if r.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token introspection failed",
            headers={"WWW-Authenticate": f'Bearer realm="{KEYCLOAK_REALM}",error="invalid_token"'},
        )

    payload = r.json()
    if not payload.get("active"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Inactive token",
            headers={"WWW-Authenticate": f'Bearer realm="{KEYCLOAK_REALM}",error="invalid_token"'},
        )

    # Enforce issuer realm
    iss = payload.get("iss")
    expected_iss = f"{KEYCLOAK_BASE_URL}/realms/{KEYCLOAK_REALM}"
    if iss != expected_iss:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token issuer mismatch",
            headers={"WWW-Authenticate": f'Bearer realm="{KEYCLOAK_REALM}",error="invalid_token"'},
        )

    # Audience / azp check
    if not _aud_ok(payload.get("aud"), payload.get("azp")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Audience not allowed",
            headers={"WWW-Authenticate": f'Bearer realm="{KEYCLOAK_REALM}",error="invalid_token"'},
        )

    return payload

# --------------------------------------------------------------------------------------
# Public dependency
# --------------------------------------------------------------------------------------
async def require_auth(
    request: Request,
    bearer: Optional[HTTPAuthorizationCredentials] = Security(http_bearer),
    oauth2_token: Optional[str] = Depends(oauth2_password),
) -> Dict[str, Any]:
    """
    Accept a token from:
      1) Authorization: Bearer <token> (normal clients, curl, Next.js),
      2) Swagger's OAuth2 password flow (via oauth2_password),
      3) Optional cookie fallback (Authorization / access_token).
    Then validate it via Keycloak introspection and return the token payload (claims).
    """
    token: Optional[str] = None

    # 1) Bearer header
    if bearer and bearer.scheme and bearer.scheme.lower() == "bearer" and bearer.credentials:
        token = bearer.credentials

    # 2) Swagger's OAuth2 password flow
    if not token and oauth2_token:
        token = oauth2_token

    # 3) Cookie fallback (if you choose to set one on responses)
    if not token:
        cookie_val = request.cookies.get("Authorization") or request.cookies.get("access_token")
        if cookie_val:
            scheme, param = get_authorization_scheme_param(cookie_val)
            token = param or cookie_val

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
            headers={"WWW-Authenticate": f'Bearer realm="{KEYCLOAK_REALM}"'},
        )

    # This call is what tests often monkeypatch:
    return _introspect(token)
