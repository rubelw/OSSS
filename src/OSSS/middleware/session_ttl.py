from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from OSSS.auth.keycloak import refresh_with_keycloak, RefreshError

EARLY_REFRESH_WINDOW = 60  # seconds
IDLE_TIMEOUT = 30 * 60     # seconds

def now() -> datetime:
    return datetime.now(timezone.utc)

class SessionTTL(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Expect a dict-like async session on request.state.session
        session = getattr(request.state, "session", None)
        if not session or not await _has_user(session):
            return await call_next(request)

        # Absolute caps (from Keycloak)
        refresh_exp: Optional[datetime] = await _get_dt(session, "refresh_expires_at")
        kc_abs: Optional[datetime] = await _get_dt(session, "kc_session_expires_at")  # optional

        absolutes = [d for d in (refresh_exp, kc_abs) if d]
        absolute_deadline = min(absolutes) if absolutes else None

        # Idle timeout
        last_seen = await _get_dt(session, "last_seen") or now()
        if (now() - last_seen).total_seconds() > IDLE_TIMEOUT:
            await session.clear()
            return Response(status_code=401)

        # Access token handling (early refresh)
        access_exp: Optional[datetime] = await _get_dt(session, "access_expires_at")
        if access_exp and (access_exp - now()).total_seconds() <= EARLY_REFRESH_WINDOW:
            refresh_token: Optional[str] = await session.get("refresh_token")
            if refresh_token:
                try:
                    tokens = await refresh_with_keycloak(refresh_token)
                    await session.set("access_token", tokens.access_token)
                    await session.set("access_expires_at", tokens.access_expires_at)
                    if tokens.refresh_token:
                        await session.set("refresh_token", tokens.refresh_token)
                    if tokens.refresh_expires_at:
                        await session.set("refresh_expires_at", tokens.refresh_expires_at)
                    await session.set("last_seen", now())
                except RefreshError:
                    await session.clear()
                    return Response(status_code=401)

        # Update session TTL in Redis to min(idle extension, absolute deadline)
        await session.set("last_seen", now())
        if absolute_deadline:
            remaining_abs = int((absolute_deadline - now()).total_seconds())
            ttl = max(0, min(remaining_abs - 30, IDLE_TIMEOUT))
        else:
            ttl = IDLE_TIMEOUT
        await session.set_ttl(ttl)

        return await call_next(request)

async def _get_dt(session, key: str) -> Optional[datetime]:
    val = await session.get(key)
    # allow both datetime objects and ISO strings
    if isinstance(val, datetime):
        return val
    if isinstance(val, str):
        try:
            return datetime.fromisoformat(val)
        except Exception:
            return None
    return None

async def _has_user(session) -> bool:
    uid = await session.get("user_id")
    return bool(uid)
