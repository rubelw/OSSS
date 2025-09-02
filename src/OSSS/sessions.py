# src/OSSS/sessions.py
from __future__ import annotations

import inspect
import json
import os
import re
import secrets
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from fastapi import Request, Response
from redis import asyncio as redis  # redis-py async API

# ⬇️ Import your central logger
from OSSS.app_logger import logger  # or: from OSSS.app_logger import get_logger; logger = get_logger(__name__)

# ---------------------------
# Config (env or settings.py)
# ---------------------------
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
SESSION_COOKIE_NAME = os.getenv("SESSION_COOKIE_NAME", "SESSION_ID")
SESSION_TTL_SECONDS = int(os.getenv("SESSION_TTL_SECONDS", "604800"))  # 7 days
COOKIE_DOMAIN = os.getenv("COOKIE_DOMAIN")
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() in {"1", "true", "yes", "on"}
COOKIE_SAMESITE = os.getenv("COOKIE_SAMESITE", "lax")

# Legacy/exported constant expected by some modules (e.g., main.py)
SESSION_PREFIX = "sess:"

SENSITIVE_KEYS = {"access_token", "refresh_token", "id_token", "password", "secret"}

# ---------------------------
# Utilities
# ---------------------------
def _redact_payload(data: Dict[str, Any]) -> Dict[str, Any]:
    redacted = {}
    for k, v in data.items():
        if k in SENSITIVE_KEYS:
            redacted[k] = "***redacted***"
        elif isinstance(v, dict):
            redacted[k] = {nk: ("***redacted***" if nk in SENSITIVE_KEYS else nv) for nk, nv in v.items()}
        else:
            redacted[k] = v
    return redacted

def _cookie_kwargs() -> Dict[str, Any]:
    kw = {
        "max_age": SESSION_TTL_SECONDS,
        "httponly": True,
        "secure": bool(COOKIE_SECURE),
        "samesite": COOKIE_SAMESITE,
        "path": "/",
    }
    if COOKIE_DOMAIN:
        kw["domain"] = COOKIE_DOMAIN
    return kw

def _safe_url(url: str) -> str:
    return re.sub(r"://([^:/]+:)?([^@]*)@", r"://***:***@", url)

def _size_bytes(s: str) -> int:
    try:
        return len(s.encode("utf-8"))
    except Exception:
        return len(s)

# ---------------------------
# Redis client holder
# ---------------------------
class RedisClient:
    _instance: Optional[redis.Redis] = None

    @classmethod
    async def get(cls) -> redis.Redis:
        if cls._instance is None:
            logger.info("redis.connect.begin", extra={"url": _safe_url(REDIS_URL)})
            cls._instance = redis.Redis.from_url(REDIS_URL, decode_responses=True)
            try:
                t0 = time.perf_counter()
                pong = await cls._instance.ping()
                dt = (time.perf_counter() - t0) * 1000
                logger.info("redis.connect.ok", extra={"pong": pong, "ms": round(dt, 2)})
            except Exception:
                logger.exception("redis.connect.error")
                raise
        return cls._instance

async def close_redis() -> None:
    """
    Gracefully close the shared async Redis client (used by app shutdown hooks).
    Safe to call multiple times.
    """
    client = RedisClient._instance
    if client is None:
        return
    try:
        # Close the client
        if hasattr(client, "close"):
            res = client.close()
            if inspect.isawaitable(res):
                await res
        # Disconnect the pool (some redis-py versions keep sockets here)
        pool = getattr(client, "connection_pool", None)
        if pool and hasattr(pool, "disconnect"):
            res = pool.disconnect()
            if inspect.isawaitable(res):
                await res
        # Null out the singleton so a future startup can reconnect cleanly
        RedisClient._instance = None
        logger.info("redis.close.ok")
    except Exception:
        logger.exception("redis.close.error")

# ---------------------------
# RedisSession wrapper
# ---------------------------
@dataclass
class RedisSession:
    client: redis.Redis
    sid: str
    prefix: str = SESSION_PREFIX
    default_ttl_sec: int = SESSION_TTL_SECONDS

    def _key(self) -> str:
        return f"{self.prefix}{self.sid}"

    async def get(self) -> Dict[str, Any]:
        t0 = time.perf_counter()
        raw = await self.client.get(self._key())
        dt = (time.perf_counter() - t0) * 1000
        if raw is None:
            logger.debug("session.get.miss", extra={"sid": self.sid, "ms": round(dt, 2)})
            return {}
        try:
            data = json.loads(raw)
            logger.debug(
                "session.get.hit",
                extra={
                    "sid": self.sid,
                    "bytes": _size_bytes(raw),
                    "ms": round(dt, 2),
                    "keys": list(data.keys()) if isinstance(data, dict) else "<non-dict>",
                },
            )
            return data if isinstance(data, dict) else {}
        except Exception:
            logger.exception("session.get.decode_error", extra={"sid": self.sid, "ms": round(dt, 2)})
            return {}

    async def set(self, data: Dict[str, Any], ttl_sec: Optional[int] = None) -> None:
        ttl = ttl_sec if ttl_sec is not None else self.default_ttl_sec
        payload = json.dumps(data, separators=(",", ":"))
        t0 = time.perf_counter()
        await self.client.setex(self._key(), ttl, payload)
        dt = (time.perf_counter() - t0) * 1000
        logger.info(
            "session.set",
            extra={
                "sid": self.sid,
                "ttl": ttl,
                "bytes": _size_bytes(payload),
                "ms": round(dt, 2),
                "preview": _redact_payload(data),
            },
        )

    async def clear(self) -> None:
        t0 = time.perf_counter()
        await self.client.delete(self._key())
        dt = (time.perf_counter() - t0) * 1000
        logger.info("session.clear", extra={"sid": self.sid, "ms": round(dt, 2)})

# ---------------------------
# FastAPI dependency
# ---------------------------
async def get_redis_session(request: Request, response: Response) -> RedisSession:
    cookie = request.cookies.get(SESSION_COOKIE_NAME)
    if cookie:
        sid = cookie
        logger.debug("cookie.found", extra={"sid": sid, "path": request.url.path, "method": request.method})
    else:
        sid = secrets.token_urlsafe(24)
        response.set_cookie(SESSION_COOKIE_NAME, sid, **_cookie_kwargs())
        logger.info("cookie.minted", extra={"sid": sid, "attrs": _cookie_kwargs(), "path": request.url.path})

    client = await RedisClient.get()
    return RedisSession(client=client, sid=sid)


# ---------------------------
# Back-compat alias & exports
# ---------------------------
async def redis_session(request: Request, response: Response) -> RedisSession:
    """Legacy alias for code that imports `redis_session`."""
    return await get_redis_session(request, response)

__all__ = [
    "RedisSession",
    "get_redis_session",
    "redis_session",   # legacy alias
    "SESSION_PREFIX",
    "close_redis",
]
