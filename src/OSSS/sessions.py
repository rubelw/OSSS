# src/OSSS/sessions.py
from __future__ import annotations

import os
import json
import logging
from typing import Any, Optional, Mapping

import redis.asyncio as redis  # pip install redis>=4.2 (includes asyncio support)
from fastapi import Request

from OSSS.app_logger import get_logger

# --------------------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------------------
REDIS_URL        = os.getenv("REDIS_URL", "redis://localhost:6379/0")
SESSION_PREFIX   = os.getenv("SESSION_PREFIX", "sess:")
SESSION_TTL_SEC  = int(os.getenv("SESSION_TTL_SEC", str(60 * 60 * 24 * 7)))  # 7 days default
MAX_CONNECTIONS  = int(os.getenv("REDIS_MAX_CONNECTIONS", "20"))
HEALTHCHECK_SECS = int(os.getenv("REDIS_HEALTHCHECK_SECS", "30"))

# Logging
SESSIONS_LOG_LEVEL = os.getenv("SESSIONS_LOG_LEVEL", "INFO").upper()
log = get_logger("sessions")
log.setLevel(getattr(logging, SESSIONS_LOG_LEVEL, logging.INFO))

def _redact_url(url: str) -> str:
    # redis://user:pass@host:port/db -> redis://***:***@host:port/db
    try:
        if "@" in url and "://" in url:
            scheme, rest = url.split("://", 1)
            creds, hostpart = rest.split("@", 1)
            if ":" in creds:
                user, _ = creds.split(":", 1)
                creds = f"{user}:***"
            else:
                creds = "***"
            return f"{scheme}://{creds}@{hostpart}"
    except Exception:
        pass
    return url

def _preview(value: Any, maxlen: int = 200) -> str:
    try:
        s = value if isinstance(value, str) else json.dumps(value, default=str)
    except Exception:
        s = str(type(value))
    s = s if len(s) <= maxlen else s[:maxlen] + "…"
    return f"{s} (len={len(s)})"

# --------------------------------------------------------------------------------------
# Session store
# --------------------------------------------------------------------------------------
class RedisSession:
    """
    Thin Redis wrapper for app session-ish storage.
    Stores JSON strings (decode_responses=True).
    """

    def __init__(
        self,
        url: str = REDIS_URL,
        prefix: str = SESSION_PREFIX,
        default_ttl: int = SESSION_TTL_SEC,
        max_connections: int = MAX_CONNECTIONS,
        health_check_interval: int = HEALTHCHECK_SECS,
    ) -> None:
        self.url = url
        self.prefix = prefix
        self.ttl = default_ttl

        self._redis: redis.Redis = redis.from_url(
            url,
            encoding="utf-8",
            decode_responses=True,
            socket_timeout=5,
            socket_connect_timeout=5,
            health_check_interval=health_check_interval,
            max_connections=max_connections,
            retry_on_timeout=True,
        )

        log.info(
            "RedisSession init: url=%s prefix=%r ttl=%ss max_conns=%d hcheck=%ds",
            _redact_url(url), prefix, default_ttl, max_connections, health_check_interval,
        )

    # -------------------- lifecycle --------------------
    async def ping(self) -> bool:
        try:
            ok = await self._redis.ping()
            log.info("RedisSession ping=%s", ok)
            return bool(ok)
        except Exception as e:
            log.exception("RedisSession ping failed: %s", e)
            raise

    async def close(self) -> None:
        try:
            await self._redis.close()
            await self._redis.connection_pool.disconnect()
            log.info("RedisSession closed and pool disconnected")
        except Exception as e:
            log.exception("RedisSession close error: %s", e)

    # -------------------- helpers ----------------------
    def _mk(self, key: str) -> str:
        k = f"{self.prefix}{key}"
        log.debug("mk_key: %r -> %r", key, k)
        return k

    # -------------------- ops --------------------------
    async def get(self, key: str) -> Optional[Any]:
        rkey = self._mk(key)
        try:
            raw = await self._redis.get(rkey)
            if raw is None:
                log.debug("GET miss key=%r", rkey)
                return None
            try:
                val = json.loads(raw)
            except Exception:
                val = raw  # not JSON? return as-is
            log.debug("GET hit key=%r type=%s preview=%s", rkey, type(val).__name__, _preview(val, 120))
            return val
        except Exception as e:
            log.exception("GET failed key=%r: %s", rkey, e)
            raise

    async def set(self, key: str, value: Any, *, ex: Optional[int] = None) -> bool:
        rkey = self._mk(key)
        ttl = ex if ex is not None else self.ttl
        try:
            sval = value if isinstance(value, str) else json.dumps(value, separators=(",", ":"), default=str)
            ok = await self._redis.set(rkey, sval, ex=ttl)
            log.info("SET key=%r ttl=%s ok=%s value_preview=%s", rkey, ttl, ok, _preview(value, 120))
            return bool(ok)
        except Exception as e:
            log.exception("SET failed key=%r: %s", rkey, e)
            raise

    async def delete(self, key: str) -> int:
        rkey = self._mk(key)
        try:
            n = await self._redis.delete(rkey)
            log.info("DEL key=%r deleted=%d", rkey, n)
            return int(n)
        except Exception as e:
            log.exception("DEL failed key=%r: %s", rkey, e)
            raise

    async def expire(self, key: str, seconds: int) -> bool:
        rkey = self._mk(key)
        try:
            ok = await self._redis.expire(rkey, seconds)
            log.debug("EXPIRE key=%r seconds=%d ok=%s", rkey, seconds, ok)
            return bool(ok)
        except Exception as e:
            log.exception("EXPIRE failed key=%r: %s", rkey, e)
            raise

    async def ttl(self, key: str) -> int:
        rkey = self._mk(key)
        try:
            t = await self._redis.ttl(rkey)
            log.debug("TTL key=%r -> %s", rkey, t)
            return int(t)
        except Exception as e:
            log.exception("TTL failed key=%r: %s", rkey, e)
            raise

    async def keys(self, pattern: str = "*") -> list[str]:
        patt = self._mk(pattern)
        try:
            ks = await self._redis.keys(patt)
            log.debug("KEYS pattern=%r -> %d keys", patt, len(ks))
            return ks
        except Exception as e:
            log.exception("KEYS failed pattern=%r: %s", patt, e)
            raise

# --------------------------------------------------------------------------------------
# App integration helpers
# --------------------------------------------------------------------------------------
def build_session_store_from_env() -> RedisSession:
    """
    Construct a RedisSession from env. Does not connect yet.
    """
    store = RedisSession(
        url=REDIS_URL,
        prefix=SESSION_PREFIX,
        default_ttl=SESSION_TTL_SEC,
        max_connections=MAX_CONNECTIONS,
        health_check_interval=HEALTHCHECK_SECS,
    )
    return store

def attach_session_store(app) -> None:
    """
    Attach a RedisSession to app.state and wire startup/shutdown checks.
    """
    if getattr(app.state, "session_store", None) is not None:
        log.warning("attach_session_store: app.state.session_store already set; replacing")

    store = build_session_store_from_env()
    app.state.session_store = store

    @app.on_event("startup")
    async def _session_startup():
        log.info("Session store startup: pinging Redis at %s", _redact_url(REDIS_URL))
        await store.ping()

    @app.on_event("shutdown")
    async def _session_shutdown():
        log.info("Session store shutdown: closing Redis client")
        await store.close()

def get_session_store(request: Request) -> RedisSession:
    """
    FastAPI dependency to inject the session store into routes / services.
    """
    store = getattr(request.app.state, "session_store", None)
    if store is None:
        raise RuntimeError("Session store not attached. Call attach_session_store(app) during app startup.")
    return store
