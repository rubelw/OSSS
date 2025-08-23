# src/OSSS/db/migrations/env.py
from __future__ import annotations

import os
import logging
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool, MetaData
from sqlalchemy.engine.url import make_url

config = context.config

# Logging from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

log = logging.getLogger("alembic.env")

# Import ONLY the metadata (avoid app side-effects)
try:
    from OSSS.models.base import Base
    target_metadata = Base.metadata
except Exception:
    target_metadata = MetaData()

# ---- helpers ---------------------------------------------------------------

def ensure_sync_url(url: str) -> str:
    """If given an async DSN (postgresql+asyncpg), switch to a sync driver for Alembic."""
    u = make_url(url)
    if u.get_backend_name() == "postgresql" and u.get_driver_name() in {"asyncpg", "aiopg"}:
        u = u.set(drivername="postgresql+psycopg2")
    return str(u)

def choose_url() -> str:
    """
    Priority:
      1) -x sqlalchemy_url=...
      2) ALEMBIC_DATABASE_URL
      3) OSSS_DATABASE_URL / OSSS_DB_URL / DATABASE_URL
      4) sqlalchemy.url from alembic.ini
      5) Built from discrete OSSS_DB_* vars (fallback)
    """
    x = context.get_x_argument(as_dictionary=True)
    if x.get("sqlalchemy_url"):
        return ensure_sync_url(x["sqlalchemy_url"])

    for env in ("ALEMBIC_DATABASE_URL", "OSSS_DATABASE_URL", "OSSS_DB_URL", "DATABASE_URL"):
        v = os.getenv(env)
        if v:
            return ensure_sync_url(v)

    ini_url = config.get_main_option("sqlalchemy.url")
    if ini_url:
        return ensure_sync_url(ini_url)

    # final fallback (matches your docker-compose defaults)
    host = os.getenv("OSSS_DB_HOST", "localhost")
    port = os.getenv("OSSS_DB_PORT", "5433")
    name = os.getenv("OSSS_DB_NAME", "osss")
    user = os.getenv("OSSS_DB_USER", "osss")
    pwd  = os.getenv("OSSS_DB_PASSWORD", "password")
    return f"postgresql+psycopg2://{user}:{pwd}@{host}:{port}/{name}"

# Allow: -x echo=true -x log=DEBUG
_x = context.get_x_argument(as_dictionary=True)
if _x.get("echo", "").lower() in {"1", "true", "yes"}:
    config.set_main_option("sqlalchemy.echo", "true")

lvl = _x.get("log", "").upper()
if lvl in {"DEBUG", "INFO", "WARNING", "ERROR"}:
    logging.getLogger("alembic").setLevel(lvl)
    logging.getLogger("sqlalchemy.engine").setLevel(lvl)

# ---- runners ---------------------------------------------------------------

def run_migrations_offline() -> None:
    url = choose_url()
    masked = url.replace(url.split("://", 1)[1].split("@")[0], "****:****")
    log.info("Running OFFLINE migrations using %s", masked)

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    url = choose_url()
    config.set_main_option("sqlalchemy.url", url)

    masked = url.replace(url.split("://", 1)[1].split("@")[0], "****:****")
    log.info("Running ONLINE migrations using %s", masked)

    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        future=True,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

