# src/OSSS/sessions.py
from __future__ import annotations
import os, json, secrets, httpx, time, logging
from datetime import datetime, timezone
from typing import Any, Optional, AsyncIterator, Dict, Iterable

import redis.asyncio as redis  # pip install "redis>=4"
from fastapi import Request
from starlette.responses import Response
from OSSS.app_logger import get_logger

log = get_logger("sessions")

SESSION_PREFIX   = os.getenv("SESSION_PREFIX", "sess:")
SESSION_TTL_SEC  = int(os.getenv("SESSION_TTL_SEC", "3600"))
SESSION_COOKIE   = os.getenv("SESSION_COOKIE", "sid")
REDIS_URL        = os.getenv("REDIS_URL", "redis://localhost:6379/0")

KC_ISSUER = os.getenv("KEYCLOAK_ISSUER") or os.getenv("OIDC_ISSUER")
KC_CLIENT_ID = os.getenv("KEYCLOAK_CLIENT_ID", "osss-api")
KC_CLIENT_SECRET = os.getenv("KEYCLOAK_CLIENT_SECRET")  # confidential client

SKIP_SESSION_PATHS: set[str] = {
    "/healthz",
    "/metrics",
    "/favicon.ico",
    "/openapi.json",
    "/docs",
    "/docs/oauth2-redirect",
    "/redoc",
    # ✅ your internal stateless endpoints (openai-proxy + AI query)
    "/v1/chat/completions",
    "/api/query",
}

# Prefix-style skips (static assets, etc.). Use prefixes for "directories".
SKIP_SESSION_PREFIXES: tuple[str, ...] = (
    "/static/",
    "/assets/",
    "/v1/",
)

def should_skip_session(request: Request) -> bool:
    """
    Centralized "stateless endpoint" check.
    This is Option A: any caller of ensure_sid_cookie_and_store() inherits this behavior.
    """
    p = request.url.path

    # exact match is safest
    if p in SKIP_SESSION_PATHS:
        return True

    # directory/prefix matches
    if SKIP_SESSION_PREFIXES and p.startswith(SKIP_SESSION_PREFIXES):
        return True

    # CORS preflight should never mint sessions
    if request.method == "OPTIONS":
        return True

    return False

class RedisSession:
    """
    Store sessions as a single JSON blob per SID at key `${prefix}${sid}`.

    Convenience helpers `set_many` and `delete_many` do read–modify–write
    updates on that JSON blob. These are *store-level* helpers (require `sid`).
    """
    def __init__(self, url: str = REDIS_URL, prefix: str = SESSION_PREFIX):
        self._r = redis.from_url(url, decode_responses=True)
        self._p = prefix
        log.info("RedisSession initialized: url=%s prefix=%s", url, prefix)

    def _k(self, key: str) -> str:
        return f"{self._p}{key}"

    async def ping(self) -> bool:
        try:
            pong = await self._r.ping()
            log.debug("Redis ping -> %s", pong)
            return bool(pong)
        except Exception as e:
            log.exception("Redis ping failed: %s", e)
            return False

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        raw = json.dumps(value) if not isinstance(value, str) else value
        await self._r.set(self._k(key), raw, ex=ttl or SESSION_TTL_SEC)
        log.debug("SET %s (ttl=%s)", self._k(key), ttl or SESSION_TTL_SEC)

    async def get(self, key: str, as_json: bool = True) -> Any:
        raw = await self._r.get(self._k(key))
        if raw is None:
            return None
        if as_json:
            try:
                return json.loads(raw)
            except Exception:
                pass
        return raw

    async def ttl(self, key: str) -> int:
        t = await self._r.ttl(self._k(key))
        log.debug("TTL %s -> %s", self._k(key), t)
        return t  # -2 missing, -1 no expire

    async def touch(self, key: str, ttl: Optional[int] = None) -> None:
        await self._r.expire(self._k(key), ttl or SESSION_TTL_SEC)
        log.debug("EXPIRE %s -> %s", self._k(key), ttl or SESSION_TTL_SEC)

    async def exists(self, key: str) -> bool:
        ok = bool(await self._r.exists(self._k(key)))
        log.debug("EXISTS %s -> %s", self._k(key), ok)
        return ok

    async def iter_keys(self, limit: int = 100) -> AsyncIterator[str]:
        patt = self._k("*")
        count = 0
        async for full in self._r.scan_iter(match=patt, count=limit):
            yield full[len(self._p):]
            count += 1
            if count >= limit:
                break

    # ---------- JSON blob convenience ops (store-level; require sid) ----------
    async def set_many(self, sid: str, mapping: Dict[str, Any], ttl: Optional[int] = None) -> Dict[str, Any]:
        """Merge `mapping` into the JSON blob at `sid` and persist."""
        cur = await self.get(sid) or {}
        if not isinstance(cur, dict):
            cur = {}
        cur.update(mapping or {})
        await self.set(sid, cur, ttl=ttl or SESSION_TTL_SEC)
        log.debug("SET_MANY sid=%s… keys=%s", sid[:8], list(mapping.keys()))
        return cur

    async def delete_many(self, sid: str, keys: Iterable[str], ttl: Optional[int] = None) -> Dict[str, Any]:
        """Delete `keys` from the JSON blob at `sid` and persist."""
        cur = await self.get(sid) or {}
        if not isinstance(cur, dict):
            cur = {}
        for k in keys:
            cur.pop(k, None)
        await self.set(sid, cur, ttl=ttl or SESSION_TTL_SEC)
        log.debug("DEL_MANY sid=%s… keys=%s", sid[:8], list(keys))
        return cur


# ---- FastAPI integration helpers ----
def _token_url() -> str:
    return f"{KC_ISSUER.rstrip('/')}/protocol/openid-connect/token"

def _basic_auth_header(cid: str, secret: str) -> dict:
    import base64
    raw = f"{cid}:{secret}".encode("utf-8")
    return {"Authorization": "Basic " + base64.b64encode(raw).decode("ascii")}

async def refresh_access_token(refresh_token: str) -> dict:
    """Return new token payload from Keycloak using refresh_token."""
    data = {"grant_type": "refresh_token", "refresh_token": refresh_token}
    headers = _basic_auth_header(KC_CLIENT_ID, KC_CLIENT_SECRET) if KC_CLIENT_SECRET else None
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(_token_url(), data=data, headers=headers)
    r.raise_for_status()
    return r.json()

async def record_tokens_to_session(
    store: RedisSession,
    sid: str,
    tokens: Dict[str, Any],
    *,
    user_email: Optional[str] = None,
    ttl: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Persist OAuth tokens + expiries into the server-side session for `sid`.
    """
    now = int(time.time())
    payload: Dict[str, Any] = {
        "access_token": tokens.get("access_token"),
        "refresh_token": tokens.get("refresh_token"),
        "expires_at": now + int(tokens.get("expires_in", 300) or 0),
        "refresh_expires_at": (now + int(tokens.get("refresh_expires_in"))) if tokens.get("refresh_expires_in") else None,
    }
    if user_email:
        payload["email"] = user_email

    updated = await store.set_many(sid, payload, ttl=ttl or SESSION_TTL_SEC)
    log.debug("Recorded tokens -> sid=%s… exp=%s", sid[:8], updated.get("expires_at"))
    return updated

async def proactive_refresh(
    store: RedisSession,
    sid: str,
    *,
    skew_seconds: int = 60,
) -> Optional[Dict[str, Any]]:
    """
    If the session access token is near expiry (<= skew), refresh it using
    the refresh_token and update the session. Returns the updated session dict
    when a refresh occurs; otherwise None.
    """
    sess = await store.get(sid) or {}
    if not isinstance(sess, dict):
        return None

    exp = sess.get("expires_at")
    rt  = sess.get("refresh_token")
    now = int(time.time())

    if not exp or not rt:
        return None

    if now + max(0, int(skew_seconds)) < int(exp):
        # not within refresh window
        return None

    try:
        new_tokens = await refresh_access_token(rt)
    except Exception as e:
        log.warning("proactive_refresh failed for sid=%s…: %s", sid[:8], e)
        return None

    updated = await record_tokens_to_session(store, sid, new_tokens)
    log.info("proactive_refresh: refreshed access token for sid=%s…", sid[:8])
    return updated


def attach_session_store(app, url: Optional[str] = None, prefix: Optional[str] = None) -> RedisSession:
    """
    Create and attach RedisSession to app.state.session_store.
    Safe to call multiple times (last wins).
    """
    store = RedisSession(url=url or REDIS_URL, prefix=prefix or SESSION_PREFIX)
    app.state.session_store = store
    log.info("Attached Redis session store to app.state.session_store")
    return store


def get_session_store(request: Request) -> RedisSession:
    store = getattr(request.app.state, "session_store", None)
    if store is None:
        # fallback (shouldn't happen if you call attach_session_store at startup)
        log.warning("session_store missing on app.state; attaching default store")
        store = attach_session_store(request.app)
    return store


async def ensure_sid_cookie_and_store(request: Request, response: Response) -> str:
    """
    Ensure a server-managed session id exists (cookie + Redis), with sliding TTL.

    Notes:
    - Stateless endpoints should not mint sessions (middleware should skip calling us,
      but we also guard here).
    - Avoid session storms if Redis is unhealthy: don't mint new SIDs on Redis errors.
    """
    # ✅ Option A: centralized bypass (works no matter who calls us)

    if should_skip_session(request):
        # Do not create sessions for stateless endpoints.
        # If a client already has a sid cookie, return it without touching Redis.

        return request.cookies.get(SESSION_COOKIE, "")

    store: RedisSession = get_session_store(request)
    sid = request.cookies.get(SESSION_COOKIE)
    created = False
    now_iso = datetime.now(timezone.utc).isoformat()

    # ---- 1) Load once (avoid exists+get roundtrip) ----
    data = None
    if sid:
        try:
            data = await store.get(sid)
        except Exception as e:
            # Redis trouble: do NOT mint a new SID every request (session storm).
            # If client has a sid, keep using it without touching Redis.
            log.warning("Session store read failed for sid=%s… (%s). Leaving cookie as-is.", sid[:8], e)
            return sid

    # ---- 2) Create if missing ----
    if not sid or data is None:
        sid = secrets.token_urlsafe(24)
        created = True
        try:
            await store.set(
                sid,
                {"created_at": now_iso},
                ttl=SESSION_TTL_SEC,
            )
            log.info("Created sid=%s… ttl=%ss", sid[:8], SESSION_TTL_SEC)
        except Exception as e:
            # If we can't persist, don't set a cookie that points to nothing.
            log.error("Session store write failed; refusing to set sid cookie (%s)", e)
            return ""

    # ---- 3) Slide TTL / last_seen ----
    if not created:
        try:
            if isinstance(data, dict):
                data = dict(data)
                data["last_seen"] = now_iso
                await store.set(sid, data, ttl=SESSION_TTL_SEC)
            else:
                # If your store supports touch, this is cheaper.
                await store.touch(sid, ttl=SESSION_TTL_SEC)
        except Exception as e:
            # Don't break the request if TTL refresh fails.
            log.warning("Session TTL refresh failed for sid=%s… (%s)", sid[:8], e)

    # ---- 4) Set cookie (created-only or sliding, your choice) ----
    # If you want true "sliding" expiration on the client too, set this cookie every time.
    SLIDE_COOKIE = os.getenv("SLIDE_SID_COOKIE", "0") == "1"

    if created or SLIDE_COOKIE:
        response.set_cookie(
            SESSION_COOKIE,
            sid,
            max_age=SESSION_TTL_SEC,
            httponly=True,
            samesite="lax",
            secure=os.getenv("COOKIE_SECURE", "0") == "1",
        )

    return sid

# small util you tried to import
async def probe_key_ttl(store: RedisSession, key: str) -> int:
    return await store.ttl(key)


__all__ = [
    "RedisSession",
    "attach_session_store",
    "get_session_store",
    "ensure_sid_cookie_and_store",
    "should_skip_session",
    "probe_key_ttl",
    "refresh_access_token",
    "record_tokens_to_session",
    "proactive_refresh",
    "SESSION_PREFIX",
    "SESSION_TTL_SEC",
    "SESSION_COOKIE",
    "REDIS_URL",
]
