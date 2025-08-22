# src/OSSS/db.py
import os
import logging
from functools import lru_cache
from contextlib import asynccontextmanager

import sqlalchemy as sa
from sqlalchemy.engine.url import make_url, URL
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

log = logging.getLogger("app")

def _mask(url: str) -> str:
    import re
    return re.sub(r'//([^:@/]+)(?::[^@/]+)?@', r'//\1:*****@', url)

def _get_env_password() -> str | None:
    # Prefer explicit vars, then fall back to common ones
    return (
        os.getenv("DB_PASSWORD")
        or os.getenv("OSSS_DB_PASSWORD")
        or os.getenv("POSTGRES_PASSWORD")
    )

def _base_parts() -> dict:
    """Return host/port/db/user from env with sensible defaults."""
    return {
        "host": os.getenv("OSSS_DB_HOST", os.getenv("POSTGRES_HOST", "127.0.0.1")),
        "port": int(os.getenv("OSSS_DB_PORT", os.getenv("POSTGRES_PORT", "5433"))),
        "db": os.getenv("OSSS_DB_NAME", os.getenv("POSTGRES_DB", "osss")),
        "user": os.getenv("OSSS_DB_USER", os.getenv("POSTGRES_USER", "osss")),
    }

def _normalize_to_async_no_pw(url_str: str | None) -> str:
    """
    Ensure driver is postgresql+asyncpg and strip any password from the URL.
    If url_str is None, build one from OSSS_* vars (without password).
    """
    if url_str:
        u = make_url(url_str)
        # Force async driver
        if u.get_backend_name() == "postgresql" and u.get_driver_name() != "asyncpg":
            u = u.set(drivername="postgresql+asyncpg")
        # Drop password if present
        if u.password is not None:
            u = URL.create(
                drivername=u.drivername,
                username=u.username,
                password=None,                     # strip
                host=u.host,
                port=u.port,
                database=u.database,
                query=u.query or {},
            )
        return str(u)

    parts = _base_parts()
    u = URL.create(
        drivername="postgresql+asyncpg",
        username=parts["user"],
        password=None,  # no password in DSN
        host=parts["host"],
        port=parts["port"],
        database=parts["db"],
    )
    return str(u)

@lru_cache
def get_async_url() -> str:
    # Respect DATABASE_URL but sanitize it
    return _normalize_to_async_no_pw(os.getenv("DATABASE_URL"))

@lru_cache
def get_engine() -> AsyncEngine:
    url = get_async_url()
    pw = _get_env_password()

    # Log where we're connecting (masked)
    try:
        u = make_url(url)
        log.info(
            "DB: connecting (driver=%s user=%s host=%s port=%s db=%s)",
            f"{u.get_backend_name()}+{u.get_driver_name()}",
            u.username, u.host, u.port, u.database,
        )
        log.info("DB: using DATABASE_URL=%s", _mask(url))
        if not pw:
            log.warning("DB: no password found in env; connection may fail.")
    except Exception:
        pass

    connect_args = {}
    if pw is not None:
        # asyncpg accepts 'password' kwarg; SQLAlchemy forwards it
        connect_args["password"] = pw

    return create_async_engine(
        url,
        pool_pre_ping=True,
        future=True,
        connect_args=connect_args,
    )

@lru_cache
def get_sessionmaker():
    return async_sessionmaker(bind=get_engine(), expire_on_commit=False, autoflush=False)

async def get_session() -> AsyncSession:
    async with get_sessionmaker()() as session:
        yield session

# --- Backward-compatibility exports ---
# Older code imports these names; alias them to the new factory functions.
AsyncSessionLocal = get_sessionmaker()   # sessionmaker[AsyncSession]
engine = get_engine()                    # AsyncEngine

# Import Base only from a metadata-only place:
from OSSS.models.base import Base  # contains just metadata/decl_base
target_metadata = Base.metadata
