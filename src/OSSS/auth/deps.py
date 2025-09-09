# src/OSSS/auth/deps.py
from __future__ import annotations
import os, time, logging
from typing import Any, Callable, Optional, Sequence

import requests
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError, ExpiredSignatureError

# ⬇️ bring in session store + refresh + helpers
from OSSS.sessions import (
    get_session_store,
    refresh_access_token,
    record_tokens_to_session,
    SESSION_COOKIE,
)
from OSSS.app_logger import get_logger

log = get_logger("auth.deps")

# ------------------------------------------------------------------------------
# Config via environment
# ------------------------------------------------------------------------------
# IMPORTANT: Set OIDC_ISSUER to the EXACT issuer your tokens use
# e.g. OIDC_ISSUER=http://host.docker.internal:8085/realms/OSSS
OIDC_ISSUER       = os.getenv("OIDC_ISSUER") or os.getenv("KEYCLOAK_ISSUER")
OIDC_CLIENT_ID    = os.getenv("OIDC_CLIENT_ID") or os.getenv("KEYCLOAK_CLIENT_ID") or "osss-api"
OIDC_JWKS_URL     = os.getenv("OIDC_JWKS_URL") or (f"{OIDC_ISSUER}/protocol/openid-connect/certs" if OIDC_ISSUER else None)
OIDC_VERIFY_AUD   = os.getenv("OIDC_VERIFY_AUD", "0") == "1"
OIDC_LEEWAY_SEC   = int(os.getenv("OIDC_LEEWAY_SEC", "60"))
AUTH_LOG_LEVEL    = os.getenv("OIDC_LOG_LEVEL", "INFO").upper()
log.setLevel(getattr(logging, AUTH_LOG_LEVEL, logging.INFO))

# HS* (local) support if you mint local tokens
JWT_SECRET         = os.getenv("JWT_SECRET")
# default still RS256, but you can broaden with env if needed
JWT_ALLOWED_ALGS   = [a.strip() for a in os.getenv("JWT_ALLOWED_ALGS", "RS256").split(",")]
JWT_LEEWAY_SECONDS = int(os.getenv("JWT_LEEWAY_SECONDS", str(OIDC_LEEWAY_SEC)))

# ---- Single source of truth for validation params (avoids drift) ----
ISSUER   = OIDC_ISSUER                 # e.g. http://host.docker.internal:8085/realms/OSSS
AUDIENCE = OIDC_CLIENT_ID              # e.g. osss-api
JWKS_URL = OIDC_JWKS_URL               # derived above

log.info(
    "AUTH cfg: issuer=%r jwks_url=%r verify_aud=%s client_id=%r allowed_algs=%s leeway=%ss",
    ISSUER, JWKS_URL, OIDC_VERIFY_AUD, AUDIENCE, JWT_ALLOWED_ALGS, JWT_LEEWAY_SECONDS
)

# ------------------------------------------------------------------------------
# JWKS cache
# ------------------------------------------------------------------------------
_JWKS_CACHE: dict[str, Any] = {}      # raw JWKS JSON: {"keys":[...]}
_JWKS_BY_KID: dict[str, dict] = {}    # kid -> JWK dict
_JWKS_EXP_AT: float = 0.0             # epoch seconds when cache expires

def _index_by_kid(data: dict[str, Any]) -> dict[str, dict]:
    by_kid: dict[str, dict] = {}
    for k in data.get("keys", []) or []:
        kid = k.get("kid")
        if kid:
            by_kid[kid] = k
    return by_kid

def _load_jwks(force: bool = False) -> dict:
    """Load JWKS (with simple TTL) and index by kid."""
    global _JWKS_CACHE, _JWKS_BY_KID, _JWKS_EXP_AT
    now = time.time()
    if not force and _JWKS_CACHE and now < _JWKS_EXP_AT:
        log.debug("JWKS cache hit (expires in %.0fs)", _JWKS_EXP_AT - now)
        return _JWKS_CACHE

    if not JWKS_URL:
        log.warning("JWKS: JWKS_URL not set; token verification disabled.")
        _JWKS_CACHE = {"keys": []}
        _JWKS_BY_KID = {}
        _JWKS_EXP_AT = now + 300
        return _JWKS_CACHE

    try:
        log.debug("JWKS: fetching %s", JWKS_URL)
        resp = requests.get(JWKS_URL, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        _JWKS_CACHE = data
        _JWKS_BY_KID = _index_by_kid(data)
        _JWKS_EXP_AT = now + 300
        log.info("JWKS: loaded %d key(s) kids=%s",
                 len(data.get("keys", [])),
                 sorted(list(_JWKS_BY_KID.keys())))
        return data
    except Exception as e:
        log.exception("JWKS fetch failed: %s", e)
        if not _JWKS_CACHE:
            _JWKS_CACHE = {"keys": []}
            _JWKS_BY_KID = {}
        _JWKS_EXP_AT = now + 60   # short backoff
        return _JWKS_CACHE

# Prime cache (non-fatal on failure)
try:
    _ = _load_jwks(force=True)
except Exception:
    pass

def _get_jwk_by_kid(kid: Optional[str], *, refresh_on_miss: bool = True) -> Optional[dict]:
    """Return JWK by kid, optionally force-refresh JWKS on miss."""
    if not kid:
        return None
    jwk = _JWKS_BY_KID.get(kid)
    if jwk:
        return jwk
    _load_jwks(force=False)
    jwk = _JWKS_BY_KID.get(kid)
    if jwk:
        return jwk
    if refresh_on_miss:
        log.warning("JWKS miss for kid=%r -> refreshing JWKS", kid)
        _load_jwks(force=True)
        jwk = _JWKS_BY_KID.get(kid)
        if jwk:
            return jwk
        log.warning("JWKS: key still not found for kid=%r; available kids=%s",
                    kid, sorted(list(_JWKS_BY_KID.keys())))
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
def verify_with_auto_refresh(token: str) -> dict:
    """
    RS/HS verification with auto-refresh of JWKS on kid miss (RS).
    Uses ISSUER/AUDIENCE defined above so iss matches your Keycloak config.
    """
    try:
        header = jwt.get_unverified_header(token)
    except Exception:
        raise AuthError("Invalid token header")

    alg = header.get("alg", "RS256")
    kid = header.get("kid")
    log.debug("JWT header: alg=%s kid=%s", alg, kid)

    if alg not in JWT_ALLOWED_ALGS:
        raise AuthError(f"Unsupported token algorithm: {alg}")

    opts = {
        "verify_aud": OIDC_VERIFY_AUD,
        "verify_exp": True,
        "verify_iss": bool(ISSUER),
        "leeway": JWT_LEEWAY_SECONDS,
    }

    # HS path
    if alg.startswith("HS"):
        if not JWT_SECRET:
            raise AuthError("Signing key not found (HS)")
        try:
            claims = jwt.decode(
                token,
                JWT_SECRET,
                algorithms=[alg],
                options=opts,
                issuer=ISSUER if ISSUER else None,
                audience=AUDIENCE if OIDC_VERIFY_AUD else None,
            )
            log.debug("JWT payload ok (HS): iss=%s sub=%s exp=%s",
                      claims.get("iss"), claims.get("sub"), claims.get("exp"))
            return claims
        except ExpiredSignatureError:
            raise AuthError("Token expired")
        except JWTError as e:
            raise AuthError(f"Invalid token (HS): {e}")

    # RS path
    jwk = _get_jwk_by_kid(kid, refresh_on_miss=True)
    if not jwk:
        raise AuthError("Unknown key (kid)")

    try:
        claims = jwt.decode(
            token,
            jwk,  # python-jose accepts JWK dict
            algorithms=[alg],
            options=opts,
            issuer=ISSUER if ISSUER else None,
            audience=AUDIENCE if OIDC_VERIFY_AUD else None,
        )
        log.debug("JWT payload ok (RS): iss=%s sub=%s exp=%s aud=%s",
                  claims.get("iss"), claims.get("sub"), claims.get("exp"), claims.get("aud"))
        return claims
    except ExpiredSignatureError:
        raise AuthError("Token expired")
    except JWTError as e:
        # Log a hint if this may be an issuer mismatch
        try:
            unverified = jwt.get_unverified_claims(token)
            log.warning("JWTError: %s (unverified iss=%r, expected=%r)",
                        e, unverified.get("iss"), ISSUER)
        except Exception:
            log.warning("JWTError: %s (could not read unverified claims)", e)
        raise AuthError(f"Invalid token (RS): {e}")


def _decode_jwt(token: str) -> dict:
    """
    Backward-compatible wrapper that delegates to verify_with_auto_refresh().
    """
    return verify_with_auto_refresh(token)

# ------------------------------------------------------------------------------
# Roles
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
# OAuth2 bearer dependency (header/cookie/proxy) with session fallback/refresh
# ------------------------------------------------------------------------------
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token", auto_error=False)

async def get_current_user(
    request: Request,
    token: str | None = Depends(oauth2_scheme),
    store = Depends(get_session_store),
) -> Optional[dict]:
    """
    Authentication flow:
      1) Try Bearer (OAuth2/Authorization header/cookie/proxy). If valid, return claims.
      2) If Bearer is missing/invalid/expired, try server session via SESSION_COOKIE.
         - If session access_token valid, use it.
         - If expired and refresh_token present, refresh via Keycloak, persist with
           record_tokens_to_session(...), then use new access_token.
      Returns claims dict or None.
    """
    # Gather a candidate Bearer
    raw = token

    # (1) Try to decode Bearer if present
    if raw:
        parts = raw.split(".")
        if len(parts) != 3:
            log.warning("Bearer header is not a JWT (segments=%d, len=%d); ignoring and using session fallback",
                        len(parts), len(raw))
            raw = None  # force session path
        else:
            try:
                claims = _decode_jwt(raw)
                claims["_roles"] = _extract_roles(claims, OIDC_CLIENT_ID)
                return claims
            except AuthError as e:
                log.debug("Bearer invalid; trying session fallback: %s", e.detail)

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

    # (1) Try to decode Bearer if present
    if raw:
        try:
            claims = _decode_jwt(raw)
            claims["_roles"] = _extract_roles(claims, OIDC_CLIENT_ID)
            return claims
        except AuthError as e:
            # fall through to session path for any invalid/expired
            log.debug("Bearer invalid; trying session fallback: %s", e.detail)

    # (2) Session fallback (works even if no Bearer at all)
    sid = request.cookies.get(SESSION_COOKIE)
    if not sid or not store:
        return None

    sess = await store.get(sid) or {}
    sess_at = sess.get("access_token")
    if sess_at:
        try:
            claims = _decode_jwt(sess_at)
            claims["_roles"] = _extract_roles(claims, OIDC_CLIENT_ID)
            return claims
        except AuthError:
            pass  # maybe expired; try refresh below

    rt = sess.get("refresh_token")
    if not rt:
        return None

    # Optional safety: only refresh when Bearer equals session access token (if both exist)
    if raw and sess_at and raw != sess_at:
        # Someone presented a different token; don't refresh session on its behalf.
        return None

    # Refresh using Keycloak
    try:
        new_tokens = await refresh_access_token(rt)
        # Persist + extend TTL via helper
        await record_tokens_to_session(
            store,
            sid,
            new_tokens,
            user_email=sess.get("email"),
        )
        claims = _decode_jwt(new_tokens["access_token"])
        claims["_roles"] = _extract_roles(claims, OIDC_CLIENT_ID)
        return claims
    except Exception as ex:
        log.warning("Session auto-refresh failed: %s", ex)
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
async def oauth2(request: Request, store = Depends(get_session_store)):
    """
    Historic dependency for routes/tests that used server-side session tokens.
    1) If Bearer header is present, try it (no refresh).
    2) Else try session (SESSION_COOKIE). If expired and refresh_token present, auto-refresh.
    """
    # (1) Raw bearer first
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:]
        try:
            return _decode_jwt(token)
        except AuthError:
            pass  # fall through

    # (2) Server-side session
    if not store:
        raise HTTPException(status_code=401, detail="Not authenticated")

    sid = request.cookies.get(SESSION_COOKIE)
    if not sid:
        raise HTTPException(status_code=401, detail="Not authenticated")

    sess = await store.get(sid) or {}
    token = sess.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        return _decode_jwt(token)
    except AuthError:
        rt = sess.get("refresh_token")
        if not rt:
            raise HTTPException(status_code=401, detail="Session expired")

        try:
            new = await refresh_access_token(rt)
        except Exception as ex:
            log.warning("refresh failed: %s", ex)
            raise HTTPException(status_code=401, detail="Session expired")

        await record_tokens_to_session(store, sid, new, user_email=sess.get("email"))
        return _decode_jwt(new["access_token"])

# ------------------------------------------------------------------------------
# Simple dependency that enforces auth
# ------------------------------------------------------------------------------
async def require_auth(user: Optional[dict] = Depends(get_current_user)) -> dict:
    if user is None:
        raise AuthError("Not authenticated")
    return user
