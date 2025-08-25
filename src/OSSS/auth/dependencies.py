# src/OSSS/auth/dependencies.py
from __future__ import annotations

import os
from typing import Any, Dict, Iterable, Optional, Set
from functools import lru_cache

import requests
from fastapi import HTTPException, Security, status
from fastapi.security import SecurityScopes
from jose import jwt, JWTError

# Use the SAME oauth2 scheme your OpenAPI references (defined in /auth_flow.py)
from OSSS.api.routers.auth_flow import oauth2_scheme


# -----------------------------------------------------------------------------
# Config
# -----------------------------------------------------------------------------
KEYCLOAK_BASE_URL = os.getenv("KEYCLOAK_BASE_URL", "http://localhost:8085").rstrip("/")
KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM", "OSSS")

# Full issuer for this realm
KEYCLOAK_ISSUER = os.getenv("KEYCLOAK_ISSUER") or f"{KEYCLOAK_BASE_URL}/realms/{KEYCLOAK_REALM}"

# Single audience to verify with jose (optional; if unset, we’ll skip jose’s aud check)
KEYCLOAK_AUDIENCE = os.getenv("KEYCLOAK_AUDIENCE")

# Accept tokens whose aud/azp matches one of these (additional guard, optional)
KEYCLOAK_ALLOWED_AUDIENCES: Set[str] = {
    c.strip()
    for c in os.getenv("KEYCLOAK_ALLOWED_AUDIENCES", "osss-api,osss-web").split(",")
    if c.strip()
}


# -----------------------------------------------------------------------------
# OIDC / JWKS helpers (cached)
# -----------------------------------------------------------------------------
@lru_cache
def _oidc_config() -> Dict[str, Any]:
    url = f"{KEYCLOAK_ISSUER}/.well-known/openid-configuration"
    resp = requests.get(url, timeout=5)
    resp.raise_for_status()
    return resp.json()


@lru_cache
def _jwks() -> Dict[str, Any]:
    resp = requests.get(_oidc_config()["jwks_uri"], timeout=5)
    resp.raise_for_status()
    return resp.json()


def _get_key(header: Dict[str, Any]) -> Dict[str, Any]:
    kid = header.get("kid")
    for k in _jwks().get("keys", []):
        if k.get("kid") == kid:
            return k
    raise HTTPException(status_code=401, detail="Unknown signing key")


def _aud_ok(aud: Any, azp: Optional[str]) -> bool:
    """
    Accept if token's `aud` (str or list) or `azp` matches any allowed audience.
    If KEYCLOAK_ALLOWED_AUDIENCES is empty, permit.
    """
    if not KEYCLOAK_ALLOWED_AUDIENCES:
        return True
    if isinstance(aud, str) and aud in KEYCLOAK_ALLOWED_AUDIENCES:
        return True
    if isinstance(aud, Iterable) and any(a in KEYCLOAK_ALLOWED_AUDIENCES for a in aud):
        return True
    if azp and azp in KEYCLOAK_ALLOWED_AUDIENCES:
        return True
    return False


def _extract_roles(claims: Dict[str, Any]) -> Set[str]:
    roles: Set[str] = set(claims.get("realm_access", {}).get("roles", []))
    for _, obj in (claims.get("resource_access") or {}).items():
        roles.update(obj.get("roles", []))
    return roles


def _extract_scopes(claims: Dict[str, Any]) -> Set[str]:
    scope_str = claims.get("scope", "")
    return set(scope_str.split()) if scope_str else set()


# -----------------------------------------------------------------------------
# Public dependencies
# -----------------------------------------------------------------------------
def get_current_user(
    security_scopes: SecurityScopes,
    token: str = Security(oauth2_scheme),
) -> Dict[str, Any]:
    """
    Decode & verify a Keycloak JWT using realm JWKS.
    Returns a user dict with roles and original claims.
    """
    try:
        header = jwt.get_unverified_header(token)
        key = _get_key(header)
        # Verify issuer always; verify audience only if configured
        claims = jwt.decode(
            token,
            key,
            algorithms=[header.get("alg", "RS256")],
            issuer=KEYCLOAK_ISSUER,
            audience=KEYCLOAK_AUDIENCE if KEYCLOAK_AUDIENCE else None,
            options={"verify_aud": bool(KEYCLOAK_AUDIENCE)},
        )
    except (JWTError, requests.RequestException) as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from e

    # Additional audience/azp guard if you provided KEYCLOAK_ALLOWED_AUDIENCES
    if KEYCLOAK_ALLOWED_AUDIENCES and not _aud_ok(claims.get("aud"), claims.get("azp")):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Audience not allowed")

    # OPTIONAL: enforce requested scopes only if both sides provide them
    required = set(security_scopes.scopes)
    provided = _extract_scopes(claims)
    if required and provided and not required.issubset(provided):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough scope")

    return {
        "sub": claims.get("sub"),
        "preferred_username": claims.get("preferred_username"),
        "email": claims.get("email"),
        "roles": sorted(_extract_roles(claims)),
        "claims": claims,
    }


# Backwards compat: some code may still depend on `require_auth`
def require_auth(user: Dict[str, Any] = Security(get_current_user)) -> Dict[str, Any]:
    """
    Thin wrapper around get_current_user so existing imports continue to work.
    """
    return user
