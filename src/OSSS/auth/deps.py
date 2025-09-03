from __future__ import annotations
import os, time, logging
from typing import Any, Callable, Optional, Sequence
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt
import requests
from jose import jwt, JWTError, ExpiredSignatureError
from OSSS.sessions import get_session_store, refresh_access_token   # your helpers

from OSSS.app_logger import get_logger

log = get_logger("auth.deps")

# ---- Config via env vars -----------------------------------------------------
OIDC_ISSUER      = os.getenv("OIDC_ISSUER") or os.getenv("KEYCLOAK_ISSUER")
OIDC_CLIENT_ID   = os.getenv("OIDC_CLIENT_ID") or os.getenv("KEYCLOAK_CLIENT_ID") or "osss-api"
OIDC_JWKS_URL    = os.getenv("OIDC_JWKS_URL") or (f"{OIDC_ISSUER}/protocol/openid-connect/certs" if OIDC_ISSUER else None)
OIDC_VERIFY_AUD  = os.getenv("OIDC_VERIFY_AUD", "0") == "1"
OIDC_LEEWAY_SEC  = int(os.getenv("OIDC_LEEWAY_SEC", "60"))
AUTH_LOG_LEVEL   = os.getenv("OIDC_LOG_LEVEL", "INFO").upper()
log.setLevel(getattr(logging, AUTH_LOG_LEVEL, logging.INFO))

JWT_SECRET      = os.getenv("JWT_SECRET")
JWT_ALLOWED_ALGS = [a.strip() for a in os.getenv("JWT_ALLOWED_ALGS","RS256").split(",")]
JWT_LEEWAY_SECONDS = int(os.getenv("JWT_LEEWAY_SECONDS", "60"))


# Dump auth config at import-time (once)
log.debug("Auth cfg: issuer=%r jwks_url=%r client_id=%r verify_aud=%s leeway=%ss",
          OIDC_ISSUER, OIDC_JWKS_URL, OIDC_CLIENT_ID, OIDC_VERIFY_AUD, OIDC_LEEWAY_SEC)



# ---- JWKS cache --------------------------------------------------------------
_JWKS_CACHE: dict[str, Any] = {}
_JWKS_EXP_AT: float = 0.0

def decode_jwt(token: str, key, audience=None, verify_aud=True):
    return jwt.decode(
        token,
        key,
        algorithms=["RS256", "HS256"],   # whatever you use
        audience=audience if verify_aud else None,
        options={"verify_aud": verify_aud, "verify_exp": True},
        leeway=JWT_LEEWAY_SECONDS,
    )

def _load_jwks(force: bool = False) -> dict:
    global _JWKS_CACHE, _JWKS_EXP_AT
    now = time.time()
    if not force and _JWKS_CACHE and now < _JWKS_EXP_AT:
        log.debug("JWKS cache hit (expires in %.0fs)", _JWKS_EXP_AT - now)
        return _JWKS_CACHE
    if not OIDC_JWKS_URL:
        log.warning("JWKS: OIDC_JWKS_URL not set; cannot verify tokens. Returning empty JWKS.")
        _JWKS_CACHE, _JWKS_EXP_AT = {"keys": []}, now + 300
        return _JWKS_CACHE
    try:
        log.debug("JWKS: fetching %s", OIDC_JWKS_URL)
        resp = requests.get(OIDC_JWKS_URL, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        _JWKS_CACHE = data
        _JWKS_EXP_AT = now + 300
        log.debug("JWKS: loaded %d keys", len(data.get("keys", [])))
        return data
    except Exception as e:
        log.exception("JWKS fetch failed: %s", e)
        if not _JWKS_CACHE:
            _JWKS_CACHE = {"keys": []}
        _JWKS_EXP_AT = now + 60
        return _JWKS_CACHE


# after computing OIDC_ISSUER, OIDC_JWKS_URL, etc.
log.info("AUTH cfg: issuer=%r jwks_url=%r verify_aud=%s client_id=%r allowed_algs=%s",
         OIDC_ISSUER, OIDC_JWKS_URL, OIDC_VERIFY_AUD, OIDC_CLIENT_ID,
         os.getenv("JWT_ALLOWED_ALGS", "RS256"))

try:
    keys = _load_jwks(force=True).get("keys", [])
    log.info("AUTH jwks: loaded %d key(s): kids=%s", len(keys), [k.get("kid") for k in keys])
except Exception:
    log.exception("AUTH jwks: initial load failed")


def _select_key(header: dict) -> Optional[dict]:
    kid = header.get("kid")
    alg = header.get("alg")
    log.debug("Token header: kid=%r alg=%r", kid, alg)
    if not kid:
        return None
    keys = _load_jwks().get("keys", [])
    for k in keys:
        if k.get("kid") == kid:
            return k
    # Try once more with force refresh
    keys = _load_jwks(force=True).get("keys", [])
    for k in keys:
        if k.get("kid") == kid:
            return k
    log.warning("decode_jwt: signing key not found for kid=%r (jwks=%r)", kid, OIDC_JWKS_URL)
    return None

# ---- Errors ------------------------------------------------------------------
class AuthError(HTTPException):
    def __init__(self, detail: str, code=status.HTTP_401_UNAUTHORIZED):
        super().__init__(status_code=code, detail=detail)



# ---- Token decode ------------------------------------------------------------
def _decode_jwt(token: str) -> dict:
    # Parse header first
    try:
        header = jwt.get_unverified_header(token)
        alg = header.get("alg", "RS256")
        kid = header.get("kid")
        log.debug("decode_jwt: header alg=%s kid=%s", alg, kid)
    except Exception:
        log.warning("decode_jwt: invalid token header")
        raise AuthError("Invalid token header")

    # HS* path (local tokens signed with shared secret)
    if alg.startswith("HS"):
        if alg not in JWT_ALLOWED_ALGS:
            log.warning("decode_jwt: HS alg %s not allowed; JWT_ALLOWED_ALGS=%s", alg, JWT_ALLOWED_ALGS)
            raise AuthError("Unsupported token algorithm")
        if not JWT_SECRET:
            log.warning("decode_jwt: HS token but JWT_SECRET not set")
            raise AuthError("Signing key not found")
        try:
            claims = jwt.decode(
                token,
                JWT_SECRET,
                algorithms=[alg],
                options={"verify_signature": True, "verify_aud": OIDC_VERIFY_AUD, "verify_iss": bool(OIDC_ISSUER)},
                issuer=OIDC_ISSUER if OIDC_ISSUER else None,
                audience=OIDC_CLIENT_ID if OIDC_VERIFY_AUD else None,
            )
            log.debug("decode_jwt: HS ok sub=%s", claims.get("sub"))
            return claims
        except Exception as e:
            log.warning("decode_jwt: HS verify failed: %s", e)
            raise AuthError("Invalid or expired token")

    # RS* path (OIDC via JWKS)
    if alg not in JWT_ALLOWED_ALGS:
        log.warning("decode_jwt: RS alg %s not allowed; JWT_ALLOWED_ALGS=%s", alg, JWT_ALLOWED_ALGS)
        raise AuthError("Unsupported token algorithm")

    key = _select_key(header)
    if not key:
        log.warning("decode_jwt: signing key not found for kid=%r (jwks=%r)", kid, OIDC_JWKS_URL)
        # IMPORTANT: don't proceed with `key=None`
        raise AuthError("Signing key not found")

    try:
        claims = jwt.decode(
            token,
            key,
            algorithms=[alg],
            options={"verify_signature": True, "verify_aud": OIDC_VERIFY_AUD, "verify_iss": bool(OIDC_ISSUER)},
            issuer=OIDC_ISSUER if OIDC_ISSUER else None,
            audience=OIDC_CLIENT_ID if OIDC_VERIFY_AUD else None,
        )
        log.debug("decode_jwt: RS ok sub=%s", claims.get("sub"))
        return claims
    except Exception as e:
        log.warning("decode_jwt: RS verify failed: %s", e)
        raise AuthError("Invalid or expired token")

# ---- Roles -------------------------------------------------------------------
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

# ---- OAuth2 only -------------------------------------------------------------
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token", auto_error=False)

async def get_current_user(request: Request, token: str | None = Depends(oauth2_scheme)) -> Optional[dict]:
    """
    Try to obtain a JWT from:
      1) OAuth2PasswordBearer (Authorization: Bearer ...)
      2) X-Forwarded-Access-Token header (if a proxy sets it)
      3) 'access_token' cookie (only if you put a *JWT* there)
    """
    log.debug("[/me] token lookup begin: path=%s", request.url.path)

    raw = token
    if raw:
        log.debug("[/me] got token from OAuth2 scheme: len=%d", len(raw))
    else:
        auth = request.headers.get("Authorization")
        log.debug("[/me] Authorization present=%s", bool(auth))
        if auth and auth.lower().startswith("bearer "):
            raw = auth.split(" ", 1)[1].strip()
            log.debug("[/me] extracted bearer from Authorization: len=%d", len(raw))

    if not raw:
        xf = request.headers.get("X-Forwarded-Access-Token")
        if xf:
            raw = xf.strip()
            log.debug("[/me] using X-Forwarded-Access-Token: len=%d", len(raw))

    if not raw:
        cookie_tok = request.cookies.get("access_token")
        if cookie_tok:
            raw = cookie_tok.strip()
            log.debug("[/me] using access_token cookie: len=%d", len(raw))

    if not raw:
        log.warning("[/me] no token found (header/cookie/proxy); unauthenticated")
        return None

    try:
        claims = _decode_jwt(raw)
        claims["_roles"] = _extract_roles(claims, OIDC_CLIENT_ID)
        log.info("[/me] authenticated sub=%s email=%s roles=%s",
                 claims.get("sub"), claims.get("email"), sorted(list(claims.get("_roles", [])))[:10])
        return claims
    except AuthError as e:
        log.warning("[/me] token present but invalid: %s", e.detail)
        return None

def ensure_access_token(request: Request) -> str:
    auth = request.headers.get("Authorization") or ""
    if not auth.lower().startswith("bearer "):
        raise AuthError("Missing bearer token")
    tok = auth.split(" ", 1)[1].strip()
    if len(tok.split(".")) != 3:
        raise AuthError("Malformed bearer token")
    return tok

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

# Back-compat shim (if anything imports oauth2)
async def oauth2(request: Request, store=Depends(get_session_store)):
    # 1) If a Bearer header is present, try it first (don’t auto-refresh unknown clients)
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:]
        try:
            return decode_jwt(token, key=...)  # your key selection
        except ExpiredSignatureError:
            # You *could* decide not to refresh here for security;
            # commonly, only refresh for your own session/cookie flow.
            pass
        except Exception:
            pass  # fall through to session

    # 2) Try your server-side session
    sid = request.cookies.get("sid")  # whatever your cookie is
    if not sid:
        raise HTTPException(status_code=401, detail="Not authenticated")

    sess = await store.get(sid) or {}
    token = sess.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        return decode_jwt(token, key=...)  # still valid
    except ExpiredSignatureError:
        # 2a) Auto-refresh if we have refresh_token
        rt = sess.get("refresh_token")
        if not rt:
            raise HTTPException(status_code=401, detail="Session expired")

        try:
            new = await refresh_access_token(rt)
        except Exception as e:
            log.warning("refresh failed: %s", e)
            raise HTTPException(status_code=401, detail="Session expired")

        # update session
        sess["access_token"]  = new["access_token"]
        sess["refresh_token"] = new.get("refresh_token", rt)
        # optional, track expiry seconds
        sess["expires_at"]    = int(time.time()) + int(new.get("expires_in", 300))

        # extend session TTL, e.g. sliding window
        await store.set(sid, sess, ttl=int(os.getenv("SESSION_TTL_SECONDS", "3600")))
        log.info("[session] refreshed access token for sid=%s", sid)

        # return decoded claims of the new token
        return decode_jwt(new["access_token"], key=...)

    # any other decode errors => 401
    except Exception:
        raise HTTPException(status_code=401, detail="Not authenticated")

# --- Simple dependency that just enforces auth -------------------------------
async def require_auth(user: Optional[dict] = Depends(get_current_user)) -> dict:
    """
    Minimal dependency for routes/tests that just need an authenticated user.
    Returns the claims dict on success; raises 401 otherwise.
    """
    if user is None:
        raise AuthError("Not authenticated")
    return user