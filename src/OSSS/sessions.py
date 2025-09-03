# src/OSSS/sessions.py
from __future__ import annotations
import os, json, secrets, httpx, time, logging, os
from datetime import datetime, timezone
from typing import Any, Optional, AsyncIterator

import redis.asyncio as redis  # pip install "redis>=4"
from fastapi import Request
from OSSS.app_logger import get_logger

log = get_logger("sessions")

SESSION_PREFIX   = os.getenv("SESSION_PREFIX", "sess:")
SESSION_TTL_SEC  = int(os.getenv("SESSION_TTL_SEC", "3600"))
SESSION_COOKIE   = os.getenv("SESSION_COOKIE", "sid")
REDIS_URL        = os.getenv("REDIS_URL", "redis://localhost:6379/0")

KC_ISSUER = os.getenv("KEYCLOAK_ISSUER") or os.getenv("OIDC_ISSUER")
KC_CLIENT_ID = os.getenv("KEYCLOAK_CLIENT_ID", "osss-api")
KC_CLIENT_SECRET = os.getenv("KEYCLOAK_CLIENT_SECRET")  # confidential client


class RedisSession:
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


async def ensure_sid_cookie_and_store(request: Request, response) -> str:
    """
    Ensure a server-managed session id exists (cookie + Redis), with sliding TTL.
    """
    store: RedisSession = get_session_store(request)
    sid = request.cookies.get(SESSION_COOKIE)
    created = False

    if not sid or not await store.exists(sid):
        sid = secrets.token_urlsafe(24)
        created = True
        await store.set(
            sid,
            {"created_at": datetime.now(timezone.utc).isoformat()},
            ttl=SESSION_TTL_SEC,
        )
        log.info("Created sid=%s… ttl=%ss", sid[:8], SESSION_TTL_SEC)
    else:
        data = await store.get(sid) or {}
        if isinstance(data, dict):
            data["last_seen"] = datetime.now(timezone.utc).isoformat()
            await store.set(sid, data, ttl=SESSION_TTL_SEC)
        else:
            await store.touch(sid, ttl=SESSION_TTL_SEC)

    if created:
        response.set_cookie(
            SESSION_COOKIE, sid, max_age=SESSION_TTL_SEC,
            httponly=True, samesite="lax",
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
    "probe_key_ttl",
    "SESSION_PREFIX",
    "SESSION_TTL_SEC",
    "SESSION_COOKIE",
    "REDIS_URL",
]
