# src/OSSS/db/session.py
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncIterator, AsyncGenerator

from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from OSSS.core.config import settings

# ---------------------------------------------------------------------------
# Engine configuration
# ---------------------------------------------------------------------------

DATABASE_URL: str | URL = settings.DATABASE_URL

# Use NullPool in tests (or when explicitly requested) to avoid sharing the same
# asyncpg connection across threads/tasks (common with TestClient).
USE_NULLPOOL = (
    os.getenv("SQLALCHEMY_NULLPOOL", "0") == "1"
    or bool(getattr(settings, "TESTING", False))
)

_engine_kwargs: dict = {
    "echo": bool(getattr(settings, "DB_ECHO", False)),
    "pool_pre_ping": True,  # protects against stale connections
}

if USE_NULLPOOL:
    _engine_kwargs["poolclass"] = NullPool

# Build the async engine once
engine = create_async_engine(DATABASE_URL, **_engine_kwargs)

# ---------------------------------------------------------------------------
# Sessionmaker (one factory for the whole app)
#   - Define AsyncSessionLocal for backwards compatibility
#   - Keep get_sessionmaker() for callers needing the factory
# ---------------------------------------------------------------------------

AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    class_=AsyncSession,
)

# Backwards-compatible alias if other code expects "_sessionmaker"
_sessionmaker: async_sessionmaker[AsyncSession] = AsyncSessionLocal

def get_engine():
    """Expose the engine (e.g., for health checks / pings)."""
    return engine

def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """Return the app-wide async sessionmaker."""
    return _sessionmaker

# ---------------------------------------------------------------------------
# FastAPI dependencies
#   - get_session: async context manager (use with `async with`)
#   - get_db: async generator (use with `Depends(get_db)`)
# ---------------------------------------------------------------------------

@asynccontextmanager
async def get_session() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
