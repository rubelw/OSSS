# src/OSSS/auth/deps.py
from __future__ import annotations

import os
import time
import logging
from typing import Any, Callable, Optional, Sequence

import requests
from requests import exceptions as req_exc
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError, ExpiredSignatureError
from urllib.parse import urlparse

from OSSS.sessions import (
    get_session_store,
    refresh_access_token,
    record_tokens_to_session,
    SESSION_COOKIE,
)
from OSSS.app_logger import get_logger

log = get_logger("OSSS.auth.deps")

# ------------------------------------------------------------------------------
# Optional discovery resolver (MUST NOT run at import time)
# ------------------------------------------------------------------------------
try:
    from OSSS.api.routers.auth_flow import _discover  # type: ignore
except Exception:
    _discover = None

# ------------------------------------------------------------------------------
# Config via environment
# ------------------------------------------------------------------------------
OIDC_ISSUER = os.getenv("OIDC_ISSUER") or os.getenv("KEYCLOAK_ISSUER")
OIDC_CLIENT_ID = os.getenv("OIDC_CLIENT_ID") or os.getenv("KEYCLOAK_CLIENT_ID") or "osss-api"

OIDC_JWKS_URL_INTERNAL = os.getenv("OIDC_JWKS_URL_INTERNAL")
OIDC_JWKS_URL_PUBLIC = os.getenv("OIDC_JWKS_URL") or (
    f"{OIDC_ISSUER}/protocol/openid-connect/certs" if OIDC_ISSUER else None
)

OIDC_VERIFY_AUD = os.getenv("OIDC_VERIFY_AUD", "0") == "1"
OIDC_VERIFY_ISS = os.getenv("OIDC_VERIFY_ISS", "1") == "1"
OIDC_LEEWAY_SEC = int(os.getenv("OIDC_LEEWAY_SEC", "60"))

AUTH_LOG_LEVEL = os.getenv("OIDC_LOG_LEVEL", "INFO").upper()
log.setLevel(getattr(logging, AUTH_LOG_LEVEL, logging.INFO))

JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALLOWED_ALGS = [a.strip() for a in os.getenv("JWT_ALLOWED_ALGS", "RS256").split(",")]
JWT_LEEWAY_SECONDS = int(os.getenv("JWT_LEEWAY_SECONDS", str(OIDC_LEEWAY_SEC)))

# ------------------------------------------------------------------------------
# Dev / local auth bypass
# ------------------------------------------------------------------------------
DISABLE_AUTH = os.getenv("OSSS_DISABLE_AUTH", "0").lower() in ("1", "true", "yes")

def _dev_user() -> dict:
    return {
        "sub": "dev-user",
        "email": "dev@example.com",
        "preferred_username": "dev",
        "_roles": {"admin", "user"},
    }

if DISABLE_AUTH:
    log.warning(
        "AUTH is DISABLED for this process (OSSS_DISABLE_AUTH=%r)",
        os.getenv("OSSS_DISABLE_AUTH"),
    )

# ------------------------------------------------------------------------------
# Import-safe static values (NO discovery, NO network)
# ------------------------------------------------------------------------------
def _issuer_static() -> Optional[str]:
    return OIDC_ISSUER

def _jwks_static() -> Optional[str]:
    if OIDC_JWKS_URL_INTERNAL:
        return OIDC_JWKS_URL_INTERNAL
    if OIDC_JWKS_URL_PUBLIC:
        return OIDC_JWKS_URL_PUBLIC
    if OIDC_ISSUER:
        return f"{OIDC_ISSUER.rstrip('/')}/protocol/openid-connect/certs"
    return None

ISSUER = _issuer_static()
JWKS_URL = _jwks_static() or ""
AUDIENCE = OIDC_CLIENT_ID

log.info(
    "AUTH cfg: issuer=%r jwks_url=%r verify_iss=%s verify_aud=%s client_id=%r allowed_algs=%s leeway=%ss",
    ISSUER,
    JWKS_URL,
    OIDC_VERIFY_ISS,
    OIDC_VERIFY_AUD,
    AUDIENCE,
    JWT_ALLOWED_ALGS,
    JWT_LEEWAY_SECONDS,
)

# ------------------------------------------------------------------------------
# Runtime-only resolvers (may do discovery / network)
# ------------------------------------------------------------------------------
def _resolve_from_discovery() -> dict[str, Any]:
    if _discover is None:
        return {}
    try:
        return _discover() or {}
    except Exception as e:
        log.debug("OIDC discovery failed: %s", e)
        return {}

def _resolve_issuer() -> Optional[str]:
    if OIDC_ISSUER:
        return OIDC_ISSUER
    return _resolve_from_discovery().get("issuer")

def _resolve_jwks_url() -> str:
    if OIDC_JWKS_URL_INTERNAL:
        return OIDC_JWKS_URL_INTERNAL
    disc = _resolve_from_discovery()
    if disc.get("jwks_uri"):
        return disc["jwks_uri"]
    if OIDC_JWKS_URL_PUBLIC:
        return OIDC_JWKS_URL_PUBLIC
    iss = _resolve_issuer()
    if iss:
        return f"{iss.rstrip('/')}/protocol/openid-connect/certs"
    return "http://keycloak:8080/realms/OSSS/protocol/openid-connect/certs"

# ------------------------------------------------------------------------------
# JWKS cache (lazy)
# ------------------------------------------------------------------------------
_JWKS_CACHE: dict[str, Any] = {}
_JWKS_BY_KID: dict[str, dict] = {}
_JWKS_EXP_AT: float = 0.0

def _index_by_kid(data: dict[str, Any]) -> dict[str, dict]:
    return {k["kid"]: k for k in data.get("keys", []) or [] if "kid" in k}

def _load_jwks(force: bool = False) -> dict:
    global _JWKS_CACHE, _JWKS_BY_KID, _JWKS_EXP_AT
    now = time.time()

    if not force and _JWKS_CACHE and now < _JWKS_EXP_AT:
        return _JWKS_CACHE

    url = _resolve_jwks_url()
    for i in range(4):
        try:
            resp = requests.get(url, timeout=5)
            resp.raise_for_status()
            data = resp.json()
            _JWKS_CACHE = data
            _JWKS_BY_KID = _index_by_kid(data)
            _JWKS_EXP_AT = now + 300
            log.info("JWKS loaded (kids=%s)", list(_JWKS_BY_KID.keys()))
            return data
        except Exception as e:
            if i == 3:
                log.error("JWKS fetch failed: %s", e)
            time.sleep(0.25 * (2 ** i))

    _JWKS_CACHE = {"keys": []}
    _JWKS_BY_KID = {}
    _JWKS_EXP_AT = now + 60
    return _JWKS_CACHE

def _get_jwk_by_kid(kid: Optional[str]) -> Optional[dict]:
    if not kid:
        return None
    jwk = _JWKS_BY_KID.get(kid)
    if jwk:
        return jwk
    _load_jwks()
    return _JWKS_BY_KID.get(kid)

# ------------------------------------------------------------------------------
# Errors
# ------------------------------------------------------------------------------
class AuthError(HTTPException):
    def __init__(self, detail: str, code: int = status.HTTP_401_UNAUTHORIZED):
        super().__init__(status_code=code, detail=detail)

# ------------------------------------------------------------------------------
# Token verification
# ------------------------------------------------------------------------------
def verify_with_auto_refresh(token: str) -> dict:
    header = jwt.get_unverified_header(token)
    alg = header.get("alg", "RS256")
    kid = header.get("kid")

    if alg not in JWT_ALLOWED_ALGS:
        raise AuthError(f"Unsupported token algorithm: {alg}")

    issuer = _resolve_issuer() if OIDC_VERIFY_ISS else None
    audience = AUDIENCE if OIDC_VERIFY_AUD else None

    opts = {
        "verify_aud": OIDC_VERIFY_AUD,
        "verify_exp": True,
        "verify_iss": bool(issuer) and OIDC_VERIFY_ISS,
        "leeway": JWT_LEEWAY_SECONDS,
    }

    if alg.startswith("HS"):
        if not JWT_SECRET:
            raise AuthError("Signing key not found")
        return jwt.decode(token, JWT_SECRET, algorithms=[alg], options=opts,
                          issuer=issuer, audience=audience)

    jwk = _get_jwk_by_kid(kid)
    if not jwk:
        raise AuthError("Unknown key (kid)")

    return jwt.decode(token, jwk, algorithms=[alg], options=opts,
                      issuer=issuer, audience=audience)

def _decode_jwt(token: str) -> dict:
    return verify_with_auto_refresh(token)

# ------------------------------------------------------------------------------
# Role helpers
# ------------------------------------------------------------------------------
def _extract_roles(claims: dict, client_id: Optional[str]) -> set[str]:
    roles: set[str] = set()
    roles.update(claims.get("realm_access", {}).get("roles", []) or [])
    if client_id:
        roles.update(
            claims.get("resource_access", {}).get(client_id, {}).get("roles", []) or []
        )
    return roles

# ------------------------------------------------------------------------------
# OAuth dependencies
# ------------------------------------------------------------------------------
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token", auto_error=False)

async def get_current_user(
    request: Request,
    token: str | None = Depends(oauth2_scheme),
    store=Depends(get_session_store),
) -> Optional[dict]:

    if DISABLE_AUTH:
        return _dev_user()

    raw = token
    if raw:
        try:
            claims = _decode_jwt(raw)
            claims["_roles"] = _extract_roles(claims, OIDC_CLIENT_ID)
            return claims
        except AuthError:
            pass

    sid = request.cookies.get(SESSION_COOKIE)
    if not sid or not store:
        return None

    sess = await store.get(sid) or {}
    at = sess.get("access_token")
    if not at:
        return None

    try:
        claims = _decode_jwt(at)
        claims["_roles"] = _extract_roles(claims, OIDC_CLIENT_ID)
        return claims
    except AuthError:
        return None

# ------------------------------------------------------------------------------
# Back-compat exports (RESTORED)
# ------------------------------------------------------------------------------
def ensure_access_token(request: Request) -> str:
    auth = request.headers.get("Authorization") or ""
    if not auth.lower().startswith("bearer "):
        raise AuthError("Missing bearer token")
    tok = auth.split(" ", 1)[1].strip()
    if len(tok.split(".")) != 3:
        raise AuthError("Malformed bearer token")
    return tok

def require_roles(
    *,
    any_of: Sequence[str] | set[str] | None = None,
    all_of: Sequence[str] | set[str] | None = None,
    client_id: Optional[str] = None,
) -> Callable[[dict], dict]:

    any_of = set(any_of or [])
    all_of = set(all_of or [])
    cid = client_id or OIDC_CLIENT_ID

    async def _dep(user: Optional[dict] = Depends(get_current_user)):
        if DISABLE_AUTH:
            return _dev_user()

        if user is None:
            raise AuthError("Not authenticated")

        roles = set(user.get("_roles") or _extract_roles(user, cid))
        if any_of and not any(r in roles for r in any_of):
            raise HTTPException(status_code=403, detail="Missing required role")
        if any(r not in roles for r in all_of):
            raise HTTPException(status_code=403, detail="Missing required role")
        return user

    return _dep

async def oauth2(request: Request, store=Depends(get_session_store)):
    if DISABLE_AUTH:
        return _dev_user()

    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        try:
            return _decode_jwt(auth.split(" ", 1)[1])
        except AuthError:
            pass

    if not store:
        raise HTTPException(status_code=401)

    sid = request.cookies.get(SESSION_COOKIE)
    if not sid:
        raise HTTPException(status_code=401)

    sess = await store.get(sid) or {}
    tok = sess.get("access_token")
    if not tok:
        raise HTTPException(status_code=401)

    return _decode_jwt(tok)

async def require_user(user: Optional[dict] = Depends(get_current_user)) -> dict:
    if DISABLE_AUTH:
        return _dev_user()
    if user is None:
        raise AuthError("Not authenticated")
    return user

async def require_auth(user: Optional[dict] = Depends(get_current_user)) -> dict:
    if DISABLE_AUTH:
        return _dev_user()
    if user is None:
        raise AuthError("Not authenticated")
    return user
