from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import httpx
from jwt import PyJWKClient, decode as jwt_decode, InvalidTokenError
from urllib.parse import urlparse, urlunparse

from .settings import settings
from .role_config import resolve_roles

def roles_dep(method: str, path: str):
    roles = resolve_roles(method, path)
    return Depends(require_realm_roles(*roles))


bearer = HTTPBearer(auto_error=True)

# ---------- URL / config ----------
def _must(name: str, val: str | None) -> str:
    if not val:
        raise RuntimeError(f"Missing required setting: {name}")
    return val

BASE = _must("KEYCLOAK_SERVER_URL", getattr(settings, "KEYCLOAK_SERVER_URL", None)).rstrip("/")
PUBLIC = (getattr(settings, "KEYCLOAK_PUBLIC_URL", None) or settings.KEYCLOAK_SERVER_URL).rstrip("/")
REALM = _must("KEYCLOAK_REALM", getattr(settings, "KEYCLOAK_REALM", None))
CLIENT_ID = _must("KEYCLOAK_CLIENT_ID", getattr(settings, "KEYCLOAK_CLIENT_ID", None))
AUDIENCE = getattr(settings, "KEYCLOAK_AUDIENCE", None) or CLIENT_ID

DISCOVERY_CANDIDATES = [
    f"{PUBLIC}/realms/{REALM}/.well-known/openid-configuration",
    f"{BASE}/realms/{REALM}/.well-known/openid-configuration",
]

# Prefer public URLs for issuer/discovery; allow explicit overrides
ISSUER = (getattr(settings, "KEYCLOAK_ISSUER", None) or f"{PUBLIC}/realms/{REALM}").rstrip("/")
WELL_KNOWN_URL = (
    getattr(settings, "KEYCLOAK_WELL_KNOWN_URL", None)
    or f"{PUBLIC}/realms/{REALM}/.well-known/openid-configuration"
)
JWKS_URL_OVERRIDE = getattr(settings, "KEYCLOAK_JWKS_URL", None)

# Optional tuning
HTTP_TIMEOUT = int(getattr(settings, "KEYCLOAK_HTTP_TIMEOUT", 5))
TLS_VERIFY = bool(getattr(settings, "KEYCLOAK_TLS_VERIFY", True))

# Simple caches
_discovery: dict | None = None
_jwks_client: PyJWKClient | None = None

def _to_public(url: str) -> str:
    """Force URL host/scheme to PUBLIC; keeps original path/query/fragment."""
    if not url:
        raise RuntimeError("Computed JWKS/Discovery URL is empty")
    p = urlparse(url)
    pub = urlparse(PUBLIC)
    return urlunparse((pub.scheme, pub.netloc, p.path, p.params, p.query, p.fragment))

async def _get_discovery():
    last = None
    async with httpx.AsyncClient(timeout=5) as c:
        for url in DISCOVERY_CANDIDATES:
            try:
                r = await c.get(url); r.raise_for_status()
                data = r.json()
                data["jwks_uri"] = _to_public(data["jwks_uri"])
                return data
            except Exception as e:
                last = e
    raise HTTPException(status_code=401, detail=f"Keycloak HTTP error: {last}")

def _swap_host(u: str, src: str, dst: str) -> str:
    if not u: return u
    up, sp, dp = urlparse(u), urlparse(src), urlparse(dst)
    if up.netloc == sp.netloc:
        return urlunparse((dp.scheme, dp.netloc, up.path, up.params, up.query, up.fragment))
    return u

async def _get_jwks_clients(disco):
    primary = disco.get("jwks_uri")
    return [u for u in {
        primary,
        _swap_host(primary, PUBLIC, BASE),
        _swap_host(primary, BASE, PUBLIC),
    } if u]

async def get_current_claims(credentials = Depends(bearer)):
    token = credentials.credentials
    disco = await _get_discovery()
    last = None
    for u in await _get_jwks_clients(disco):
        try:
            key = PyJWKClient(u).get_signing_key_from_jwt(token).key
            return jwt_decode(token, key, algorithms=["RS256"],
                              audience=AUDIENCE or None, issuer=f"{PUBLIC}/realms/{REALM}",
                              options={"verify_aud": bool(AUDIENCE)})
        except Exception as e:
            last = e
            continue
    raise HTTPException(status_code=401, detail=f"Token validation error: {last}")

# ---- Authorization helpers (unchanged) ----
def _403(msg: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=msg)

def require_realm_roles(*required_roles: str):
    """
    Dependency factory: ensures the caller has ALL of the given realm roles.
    """
    async def _dep(claims=Depends(get_current_claims)):
        roles = set((claims or {}).get("realm_access", {}).get("roles") or [])
        missing = [r for r in required_roles if r not in roles]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient realm role(s): {', '.join(missing)}",
            )
        return True

    return _dep


def roles_dep_for(method: str, path: str):
    """
    Convenience wrapper: looks up roles from role-rules.yaml (or JSON)
    and returns a FastAPI Depends(...) you can drop into `dependencies=[...]`.
    """
    roles = resolve_roles(method, path)
    return Depends(require_realm_roles(*roles))

def require_any_realm_role(*roles: str):
    def _dep(claims: dict = Depends(get_current_claims)) -> dict:
        have = set(claims.get("realm_access", {}).get("roles", []) or [])
        if have.intersection(roles):
            return claims
        raise _403(f"Requires any realm role in: {', '.join(roles)}")
    return _dep

def require_client_roles(*roles: str, client_id: str | None = None):
    client = client_id or settings.KEYCLOAK_CLIENT_ID
    def _dep(claims: dict = Depends(get_current_claims)) -> dict:
        have = set(claims.get("resource_access", {}).get(client, {}).get("roles", []) or [])
        need = set(roles)
        if need.issubset(have):
            return claims
        raise _403(f"Missing client role(s) on '{client}': {', '.join(sorted(need - have))}")
    return _dep

def require_any_client_role(*roles: str, client_id: str | None = None):
    client = client_id or settings.KEYCLOAK_CLIENT_ID
    def _dep(claims: dict = Depends(get_current_claims)) -> dict:
        have = set(claims.get("resource_access", {}).get(client, {}).get("roles", []) or [])
        if have.intersection(roles):
            return claims
        raise _403(f"Requires any client role on '{client}' in: {', '.join(roles)}")
    return _dep

def require_groups(*groups: str):
    def _dep(claims: dict = Depends(get_current_claims)) -> dict:
        have = set(claims.get("groups", []) or [])
        need = set(groups)
        if need.issubset(have):
            return claims
        raise _403(f"Missing group(s): {', '.join(sorted(need - have))}")
    return _dep

def require_scopes(*scopes: str):
    def _dep(claims: dict = Depends(get_current_claims)) -> dict:
        raw = claims.get("scope") or claims.get("scp") or []
        have = set(raw.split()) if isinstance(raw, str) else set(raw)
        need = set(scopes)
        if need.issubset(have):
            return claims
        raise _403(f"Missing scope(s): {', '.join(sorted(need - have))}")
    return _dep

__all__ = [
    "get_current_claims",
    "require_realm_roles",
    "require_any_realm_role",
    "require_client_roles",
    "require_any_client_role",
    "require_groups",
    "require_scopes",
]
