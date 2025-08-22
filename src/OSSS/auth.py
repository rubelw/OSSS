# src/OSSS/auth.py
from __future__ import annotations

import os
from typing import Any, Dict, Optional, Tuple, Iterable

import requests
from fastapi import HTTPException, status, Security, Depends, Request
from fastapi.security import (
    HTTPBearer,
    HTTPAuthorizationCredentials,
    OAuth2PasswordBearer,
)
from fastapi.security.utils import get_authorization_scheme_param
from urllib.parse import urlparse

# ---------- Configuration ----------
AUTH_DEBUG = os.getenv("AUTH_DEBUG", "0") == "1"

KEYCLOAK_BASE_URL = os.getenv("KEYCLOAK_BASE_URL", "http://localhost:8085").rstrip("/")
KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM", "OSSS")
KEYCLOAK_PUBLIC_URL = os.getenv("KEYCLOAK_PUBLIC_URL", KEYCLOAK_BASE_URL).rstrip("/")


# Confidential client used for introspection (must have permission to introspect)
INTROSPECT_CLIENT_ID = os.getenv("KEYCLOAK_CLIENT_ID", "osss-api")
INTROSPECT_CLIENT_SECRET = os.getenv("KEYCLOAK_CLIENT_SECRET", "changeme")

# Accept tokens for ANY of these audiences or authorized party (azp)
ALLOWED_AUDIENCES: Set[str] = {
    c.strip() for c in os.getenv("KEYCLOAK_ALLOWED_AUDIENCES", "osss-api").split(",") if c.strip()
}

INTROSPECTION_URL = (
    f"{KEYCLOAK_BASE_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/token/introspect"
)

AUTH_DEBUG = os.getenv("AUTH_DEBUG", "0") == "1"

# ---------- Security schemes (docs + runtime) ----------
# Shown in Swagger's "Authorize" dialog (password flow)
oauth2_password = OAuth2PasswordBearer(
    tokenUrl="/token",
    auto_error=False,  # don't auto-401; we'll assemble a better error
)

# Parses Authorization: Bearer <token>
http_bearer = HTTPBearer(auto_error=False)

# ---------- Helpers ----------
def _parse_bearer(authorization: Optional[str]) -> str:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    scheme, param = get_authorization_scheme_param(authorization)
    if scheme.lower() != "bearer" or not param:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return param

def _same_host(a: str, b: str) -> bool:
    pa, pb = urlparse(a), urlparse(b)
    # treat localhost/127.0.0.1/::1 as equivalent in dev
    def norm(h: str) -> str:
        return "localhost" if h in {"127.0.0.1", "::1"} else h
    return (pa.scheme, norm(pa.hostname or ""), pa.port) == (pb.scheme, norm(pb.hostname or ""), pb.port)

def _issuer_ok(iss: str) -> bool:
    want = f"{KEYCLOAK_BASE_URL}/realms/{KEYCLOAK_REALM}"
    want_pub = f"{KEYCLOAK_PUBLIC_URL}/realms/{KEYCLOAK_REALM}"
    return iss == want or iss == want_pub or _same_host(iss, want) or _same_host(iss, want_pub)

def _introspect(token: str) -> Dict[str, Any]:
    data = {
        "token": token,
        "client_id": INTROSPECT_CLIENT_ID,
        "client_secret": INTROSPECT_CLIENT_SECRET,
    }
    try:
        r = requests.post(INTROSPECTION_URL, data=data, timeout=10)
    except requests.RequestException:
        if AUTH_DEBUG:
            print("[auth] introspection request failed")
        raise HTTPException(status_code=502, detail="Keycloak introspection unavailable")

    if AUTH_DEBUG:
        print("[auth] introspection status:", r.status_code)
        try:
            print("[auth] payload:", r.json())
        except Exception:
            print("[auth] non-JSON:", r.text[:300])

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

    iss = payload.get("iss") or ""
    if not _issuer_ok(iss):
        if AUTH_DEBUG:
            print("[auth] issuer mismatch:", iss)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token issuer mismatch",
            headers={"WWW-Authenticate": f'Bearer realm="{KEYCLOAK_REALM}",error="invalid_token"'},
        )

    if not _aud_ok(payload.get("aud"), payload.get("azp")):
        if AUTH_DEBUG:
            print("[auth] audience/azp not allowed:", payload.get("aud"), payload.get("azp"))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Audience not allowed",
            headers={"WWW-Authenticate": f'Bearer realm="{KEYCLOAK_REALM}",error="invalid_token"'},
        )

    return payload

def _aud_ok(aud: Any, azp: Optional[str]) -> bool:
    """
    Accept if token's `aud` contains any allowed audience OR `azp` matches.
    Keycloak may emit aud as str or list.
    """
    if isinstance(aud, str):
        if aud in ALLOWED_AUDIENCES:
            return True
    elif isinstance(aud, Iterable):
        if any(a in ALLOWED_AUDIENCES for a in aud):
            return True
    if azp and azp in ALLOWED_AUDIENCES:
        return True
    return False

def _introspect(token: str) -> dict:
    def _post(use_basic: bool):
        data = {"token": token}
        if use_basic:
            # HTTP Basic: credentials in Authorization header
            return requests.post(
                INTROSPECTION_URL, data=data,
                auth=(INTROSPECT_CLIENT_ID, INTROSPECT_CLIENT_SECRET),
                timeout=10,
            )
        else:
            # Credentials in form body
            data_with_creds = {
                **data,
                "client_id": INTROSPECT_CLIENT_ID,
                "client_secret": INTROSPECT_CLIENT_SECRET,
            }
            return requests.post(INTROSPECTION_URL, data=data_with_creds, timeout=10)

    # Try form creds first, then Basic as a fallback
    r = _post(use_basic=False)
    if r.status_code in (400, 401, 403):
        if AUTH_DEBUG:
            print("[auth] Introspection (form creds) failed:",
                  r.status_code, r.text[:300])
        r = _post(use_basic=True)

    if AUTH_DEBUG:
        print("[auth] Introspection status:", r.status_code)

    if r.status_code != 200:
        # Bad client creds or client not allowed to introspect
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token introspection failed",
            headers={"WWW-Authenticate": f'Bearer realm="{KEYCLOAK_REALM}",error="invalid_token"'},
        )

    try:
        payload = r.json()
    except json.JSONDecodeError:
        if AUTH_DEBUG:
            print("[auth] Introspection returned non-JSON:", r.text[:300])
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": f'Bearer realm="{KEYCLOAK_REALM}",error="invalid_token"'},
        )

    if AUTH_DEBUG:
        print("[auth] Introspection payload keys:", list(payload.keys()))

    if not payload.get("active"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Inactive token",
            headers={"WWW-Authenticate": f'Bearer realm="{KEYCLOAK_REALM}",error="invalid_token"'},
        )

    # Issuer check
    iss = payload.get("iss")
    expected_iss = f"{KEYCLOAK_BASE_URL}/realms/{KEYCLOAK_REALM}"
    if iss != expected_iss:
        if AUTH_DEBUG:
            print("[auth] Issuer mismatch. got:", iss, "expected:", expected_iss)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token issuer mismatch",
            headers={"WWW-Authenticate": f'Bearer realm="{KEYCLOAK_REALM}",error="invalid_token"'},
        )

    # Audience/azp check
    aud = payload.get("aud")
    azp = payload.get("azp")
    if AUTH_DEBUG:
        print("[auth] allowed audiences:", ALLOWED_AUDIENCES, "aud:", aud, "azp:", azp)
    if not _aud_ok(aud, azp):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Audience not allowed",
            headers={"WWW-Authenticate": f'Bearer realm="{KEYCLOAK_REALM}",error="invalid_token"'},
        )

    return payload

# ---------- Public dependencies ----------
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
    Also enforces KEYCLOAK_ALLOWED_AUDIENCES against `aud` / `azp`.
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

    # Introspect with Keycloak
    payload = _introspect(token)

    # ---- SAFETY GUARD: handle None / non-dict payloads cleanly ----
    if not isinstance(payload, dict):
        if AUTH_DEBUG:
            print("[auth] Introspection returned non-dict/empty payload:", repr(payload))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": f'Bearer realm="{KEYCLOAK_REALM}",error="invalid_token"'},
        )

    # Enforce allowed audiences (aud or azp) — tolerate missing keys
    aud = payload.get("aud")
    azp = payload.get("azp")

    if AUTH_DEBUG:
        print("[auth] allowed audiences:", ALLOWED_AUDIENCES)
        print("[auth] token aud:", aud, "azp:", azp)

    if not _aud_ok(aud, azp):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Audience not allowed",
            headers={"WWW-Authenticate": f'Bearer realm="{KEYCLOAK_REALM}",error="invalid_token"'},
        )

    return payload

def require_realm_role(role: str):
    """
    Dependency that enforces a Keycloak realm role on top of require_auth.
    Works if the introspection payload includes realm roles; otherwise adjust to your mapping.
    """
    def _dep(claims: Dict[str, Any] = Depends(require_auth)) -> Dict[str, Any]:
        roles = ((claims.get("realm_access") or {}).get("roles")) or []
        if role not in roles:
            raise HTTPException(status_code=403, detail=f"Missing required realm role: {role}")
        return claims
    return _dep

__all__ = ["require_auth", "oauth2_password", "require_realm_role"]
