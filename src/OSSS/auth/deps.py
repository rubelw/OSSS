# src/OSSS/auth/deps.py
from __future__ import annotations
import os, time, logging
from typing import Any, Callable, Optional, Sequence

import requests
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError, ExpiredSignatureError

from OSSS.sessions import get_session_store, refresh_access_token   # project helpers
from OSSS.app_logger import get_logger

log = get_logger("auth.deps")

# ------------------------------------------------------------------------------
# Config via environment
# ------------------------------------------------------------------------------
OIDC_ISSUER       = os.getenv("OIDC_ISSUER") or os.getenv("KEYCLOAK_ISSUER")
OIDC_CLIENT_ID    = os.getenv("OIDC_CLIENT_ID") or os.getenv("KEYCLOAK_CLIENT_ID") or "osss-api"
OIDC_JWKS_URL     = os.getenv("OIDC_JWKS_URL") or (f"{OIDC_ISSUER}/protocol/openid-connect/certs" if OIDC_ISSUER else None)
OIDC_VERIFY_AUD   = os.getenv("OIDC_VERIFY_AUD", "0") == "1"
OIDC_LEEWAY_SEC   = int(os.getenv("OIDC_LEEWAY_SEC", "60"))
AUTH_LOG_LEVEL    = os.getenv("OIDC_LOG_LEVEL", "INFO").upper()
log.setLevel(getattr(logging, AUTH_LOG_LEVEL, logging.INFO))

# HS* (local) support if you mint local tokens
JWT_SECRET         = os.getenv("JWT_SECRET")
JWT_ALLOWED_ALGS   = [a.strip() for a in os.getenv("JWT_ALLOWED_ALGS", "RS256").split(",")]
JWT_LEEWAY_SECONDS = int(os.getenv("JWT_LEEWAY_SECONDS", str(OIDC_LEEWAY_SEC)))

# Dump auth config once
log.info(
    "AUTH cfg: issuer=%r jwks_url=%r verify_aud=%s client_id=%r allowed_algs=%s leeway=%ss",
    OIDC_ISSUER, OIDC_JWKS_URL, OIDC_VERIFY_AUD, OIDC_CLIENT_ID, JWT_ALLOWED_ALGS, JWT_LEEWAY_SECONDS
)

# ------------------------------------------------------------------------------
# JWKS cache
# ------------------------------------------------------------------------------
_JWKS_CACHE: dict[str, Any] = {}
_JWKS_EXP_AT: float = 0.0

def _load_jwks(force: bool = False) -> dict:
    global _JWKS_CACHE, _JWKS_EXP_AT
    now = time.time()
    if not force and _JWKS_CACHE and now < _JWKS_EXP_AT:
        log.debug("JWKS cache hit (expires in %.0fs)", _JWKS_EXP_AT - now)
        return _JWKS_CACHE

    if not OIDC_JWKS_URL:
        log.warning("JWKS: OIDC_JWKS_URL not set; token verification disabled.")
        _JWKS_CACHE, _JWKS_EXP_AT = {"keys": []}, now + 300
        return _JWKS_CACHE

    try:
        log.debug("JWKS: fetching %s", OIDC_JWKS_URL)
        resp = requests.get(OIDC_JWKS_URL, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        _JWKS_CACHE = data
        _JWKS_EXP_AT = now + 300
        log.info("JWKS: loaded %d key(s)", len(data.get("keys", [])))
        return data
    except Exception as e:
        log.exception("JWKS fetch failed: %s", e)
        # preserve last cache if present; else install empty
        if not _JWKS_CACHE:
            _JWKS_CACHE = {"keys": []}
        _JWKS_EXP_AT = now + 60
        return _JWKS_CACHE

# Prime cache once (non-fatal)
try:
    _ = _load_jwks(force=True)
except Exception:
    pass

def _select_key(header: dict) -> Optional[dict]:
    kid = (header or {}).get("kid")
    if not kid:
        return None
    keys = _load_jwks().get("keys", [])
    for k in keys:
        if k.get("kid") == kid:
            return k
    keys = _load_jwks(force=True).get("keys", [])
    for k in keys:
        if k.get("kid") == kid:
            return k
    log.warning("JWKS: key not found for kid=%r", kid)
    return None

# ------------------------------------------------------------------------------
# Errors
# ------------------------------------------------------------------------------
class AuthError(HTTPException):
    def __init__(self, detail: str, code: int = status.HTTP_401_UNAUTHORIZED):
        super().__init__(status_code=code, detail=detail)

# ------------------------------------------------------------------------------
# Token decode (supports RS* via JWKS and HS* via shared secret)
# ------------------------------------------------------------------------------
def _decode_jwt(token: str) -> dict:
    try:
        header = jwt.get_unverified_header(token)
    except Exception:
        raise AuthError("Invalid token header")

    alg = header.get("alg", "RS256")
    if alg not in JWT_ALLOWED_ALGS:
        raise AuthError("Unsupported token algorithm")

    # Common decode options (put leeway INSIDE options)
    opts = {
        "verify_aud": OIDC_VERIFY_AUD,
        "verify_exp": True,
        "verify_iss": bool(OIDC_ISSUER),
        "leeway": JWT_LEEWAY_SECONDS,
    }

    # HS path (local)
    if alg.startswith("HS"):
        if not JWT_SECRET:
            raise AuthError("Signing key not found")
        try:
            claims = jwt.decode(
                token,
                JWT_SECRET,
                algorithms=[alg],
                options=opts,
                issuer=OIDC_ISSUER if OIDC_ISSUER else None,
                audience=OIDC_CLIENT_ID if OIDC_VERIFY_AUD else None,
            )
            return claims
        except ExpiredSignatureError:
            raise AuthError("Token expired")
        except JWTError:
            raise AuthError("Invalid token")

    # RS path (OIDC/JWKS)
    key = _select_key(header)
    if not key:
        raise AuthError("Signing key not found")

    try:
        claims = jwt.decode(
            token,
            key,  # python-jose accepts JWK dict for RS*
            algorithms=[alg],
            options=opts,
            issuer=OIDC_ISSUER if OIDC_ISSUER else None,
            audience=OIDC_CLIENT_ID if OIDC_VERIFY_AUD else None,
        )
        return claims
    except ExpiredSignatureError:
        raise AuthError("Token expired")
    except JWTError:
        raise AuthError("Invalid token")

# ------------------------------------------------------------------------------
# Roles extraction
# ------------------------------------------------------------------------------
def _extract_roles(claims: dict, client_id: Optional[str]) -> set[str]:
    roles: set[str] = set()
    try:
        roles.update(claims.get("realm_access", {}).get("roles", []) or [])
    except Exception:
        pass
    if client_id:
        try:
            roles.update(claims.get("resource_access", {}).get(client_id, {}).get("roles", []) or [])
        except Exception:
            pass
    return roles

# ------------------------------------------------------------------------------
# OAuth2 bearer dependency (header/cookie/proxy)
# ------------------------------------------------------------------------------
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token", auto_error=False)

async def get_current_user(request: Request, token: str | None = Depends(oauth2_scheme)) -> Optional[dict]:
    """
    Pull a JWT from:
      1) OAuth2PasswordBearer (Authorization: Bearer ...)
      2) Authorization header (if not provided via dependency)
      3) X-Forwarded-Access-Token (proxy)
      4) 'access_token' cookie (JWT only)
    Returns decoded claims dict or None if not authenticated/invalid.
    """
    raw = token

    if not raw:
        auth = request.headers.get("Authorization", "")
        if auth.lower().startswith("bearer "):
            raw = auth.split(" ", 1)[1].strip()

    if not raw:
        xf = request.headers.get("X-Forwarded-Access-Token")
        if xf:
            raw = xf.strip()

    if not raw:
        cookie_tok = request.cookies.get("access_token")
        if cookie_tok:
            raw = cookie_tok.strip()

    if not raw:
        # unauthenticated; caller can decide whether to require
        return None

    try:
        claims = _decode_jwt(raw)
        claims["_roles"] = _extract_roles(claims, OIDC_CLIENT_ID)
        # Trim noisy logs by default
        log.info("[/me] authenticated sub=%s email=%s roles=%s",
                 claims.get("sub"), claims.get("email"),
                 sorted(list(claims.get("_roles", [])))[:10])
        return claims
    except AuthError as e:
        log.debug("Bearer presented but invalid: %s", e.detail)
        return None
    except Exception as e:
        # Harden against unexpected decode errors (don’t 500)
        log.exception("Unexpected token decode error: %s", e)
        return None

def ensure_access_token(request: Request) -> str:
    auth = request.headers.get("Authorization") or ""
    if not auth.lower().startswith("bearer "):
        raise AuthError("Missing bearer token")
    tok = auth.split(" ", 1)[1].strip()
    if len(tok.split(".")) != 3:
        raise AuthError("Malformed bearer token")
    return tok

# ------------------------------------------------------------------------------
# Role requirement
# ------------------------------------------------------------------------------
def require_roles(*, any_of: Sequence[str] | set[str] | None = None,
                  all_of: Sequence[str] | set[str] | None = None,
                  client_id: Optional[str] = None) -> Callable[[dict], dict]:
    any_of = set(any_of or [])
    all_of = set(all_of or [])
    cid = client_id or OIDC_CLIENT_ID

    async def _dep(user: Optional[dict] = Depends(get_current_user)):
        if user is None:
            raise AuthError("Not authenticated")
        roles = set(user.get("_roles") or _extract_roles(user, cid))
        missing_all = [r for r in all_of if r not in roles]
        missing_any = bool(any_of) and not any(r in roles for r in any_of)
        if missing_all or missing_any:
            detail = {
                "error": "missing_required_roles",
                "need_all_of": sorted(list(all_of)) if all_of else [],
                "need_any_of": sorted(list(any_of)) if any_of else [],
                "have": sorted(list(roles))[:20],
            }
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)
        return user

    return _dep

# ------------------------------------------------------------------------------
# Back-compat “oauth2” shim with session-based auto-refresh
# ------------------------------------------------------------------------------
async def oauth2(request: Request, store=Depends(get_session_store)):
    """
    Historic dependency for routes/tests that used server-side session tokens.
    1) If Bearer header is present, try it (no refresh).
    2) Else try session (sid cookie). If expired and refresh_token present, auto-refresh.
    """
    # (1) Raw bearer first
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:]
        try:
            return _decode_jwt(token)
        except AuthError:
            # fall back to session path below
            pass

    # (2) Server-side session
    if not store:
        raise HTTPException(status_code=401, detail="Not authenticated")

    sid = request.cookies.get("sid")  # your cookie name
    if not sid:
        raise HTTPException(status_code=401, detail="Not authenticated")

    sess = await store.get(sid) or {}
    token = sess.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        # still valid?
        return _decode_jwt(token)
    except AuthError as e:
        # attempt refresh if we have a refresh_token
        rt = sess.get("refresh_token")
        if not rt:
            raise HTTPException(status_code=401, detail="Session expired")

        try:
            new = await refresh_access_token(rt)
        except Exception as ex:
            log.warning("refresh failed: %s", ex)
            raise HTTPException(status_code=401, detail="Session expired")

        # update session and extend TTL (sliding window)
        sess["access_token"]  = new["access_token"]
        sess["refresh_token"] = new.get("refresh_token", rt)
        sess["expires_at"]    = int(time.time()) + int(new.get("expires_in", 300))
        ttl = int(os.getenv("SESSION_TTL_SECONDS", "3600"))
        await store.set(sid, sess, ttl=ttl)
        log.info("[session] refreshed access token for sid=%s", sid[:6] + "…")

        return _decode_jwt(new["access_token"])

# ------------------------------------------------------------------------------
# Simple dependency that enforces auth
# ------------------------------------------------------------------------------
async def require_auth(user: Optional[dict] = Depends(get_current_user)) -> dict:
    if user is None:
        raise AuthError("Not authenticated")
    return user
