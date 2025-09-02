# src/OSSS/sessions.py
from __future__ import annotations
from fastapi import Request
from redis.asyncio import Redis
import secrets, json, contextlib

SESSION_PREFIX = "sess:"  # redis key prefix

class RedisSession:
    def __init__(self, redis: Redis, sid: str, ttl: int):
        self.redis = redis
        self.sid = sid
        self.key = f"{SESSION_PREFIX}{sid}"
        self.ttl = ttl

    async def get(self) -> dict:
        raw = await self.redis.get(self.key)
        return json.loads(raw) if raw else {}

    async def set(self, data: dict) -> None:
        await self.redis.set(self.key, json.dumps(data), ex=self.ttl)

    async def update(self, **kwargs) -> dict:
        data = await self.get()
        data.update(kwargs)
        await self.set(data)
        return data

    async def clear(self) -> None:
        await self.redis.delete(self.key)

async def redis_session(request: Request, redis: Redis, ttl: int) -> RedisSession:
    # Ensure a session id lives inside the cookie-signed request.session
    sid = request.session.get("sid")
    if not sid:
        sid = secrets.token_urlsafe(32)
        request.session["sid"] = sid
    # Sliding expiration: touch TTL on each request
    rs = RedisSession(redis, sid, ttl)
    with contextlib.suppress(Exception):
        await rs.redis.expire(rs.key, ttl)
    return rs
