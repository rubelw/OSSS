# src/OSSS/db/session.py
from __future__ import annotations

import os
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.engine import URL
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
    # "future": True,  # SQLAlchemy 2.x defaults; not needed explicitly
}

if USE_NULLPOOL:
    _engine_kwargs["poolclass"] = NullPool

# Build the async engine once
engine = create_async_engine(DATABASE_URL, **_engine_kwargs)

# ---------------------------------------------------------------------------
# Sessionmaker (one factory for the whole app)
# ---------------------------------------------------------------------------

_sessionmaker: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    class_=AsyncSession,
)

def get_engine():
    """Expose the engine (e.g., for health checks / pings)."""
    return engine

def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """Return the app-wide async sessionmaker."""
    return _sessionmaker

# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------

async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Yield a fresh AsyncSession per request.

    Notes:
    - Do not run concurrent queries on the same session (no asyncio.gather on one session).
    - Commit explicitly in endpoints/services if you mutate. This dependency does not auto-commit.
    """
    async with _sessionmaker() as session:
        try:
            yield session
        except Exception:
            # Roll back on error to leave the connection clean for the pool
            await session.rollback()
            raise
        finally:
            await session.close()
