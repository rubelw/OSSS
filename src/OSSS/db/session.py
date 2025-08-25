# src/OSSS/db/session.py
from __future__ import annotations

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.engine import URL

from OSSS.core.config import settings

# Build the async engine once
# DATABASE_URL should be async (e.g., postgresql+asyncpg://...)
DATABASE_URL: str | URL = settings.DATABASE_URL
engine = create_async_engine(DATABASE_URL, echo=getattr(settings, "DB_ECHO", False), future=True)

# Create a single async sessionmaker for the app
_sessionmaker: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """Return the app-wide async sessionmaker."""
    return _sessionmaker


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields an AsyncSession.
    Note: call the sessionmaker (factory) to create a session instance.
    """
    maker = get_sessionmaker()  # <- factory
    async with maker() as session:  # <- session instance
        yield session
