# src/OSSS/db/session.py
from __future__ import annotations
import logging
from functools import lru_cache
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from .base import Base
from OSSS.core.config import settings

log = logging.getLogger(__name__)

@lru_cache
def get_engine():
    log.info("DB: connecting (url=%s)", settings.DATABASE_URL.replace(settings.DATABASE_URL.split('@')[0], "postgresql+asyncpg://***:***"))
    return create_async_engine(settings.DATABASE_URL, pool_pre_ping=True, future=True)

@lru_cache
def get_sessionmaker():
    return async_sessionmaker(bind=get_engine(), expire_on_commit=False, autoflush=False)

async def get_session() -> AsyncSession:
    async with get_sessionmaker()() as session:
        yield session
