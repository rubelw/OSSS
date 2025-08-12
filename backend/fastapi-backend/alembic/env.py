# alembic/env.py (relevant bits)
import os, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.models.base import Base, GUID, JSONB


config = context.config
target_metadata = Base.metadata

def _get_sync_url() -> str:
    url = os.getenv("ALEMBIC_DATABASE_URL") or config.get_main_option("sqlalchemy.url")
    if not url:
        async_url = os.getenv("DATABASE_URL", "")
        if async_url.startswith("postgresql+asyncpg://"):
            url = async_url.replace("+asyncpg", "+psycopg2")
    if not url:
        raise RuntimeError("No sync DB URL for Alembic")
    return url

def run_migrations_offline():
    context.configure(url=_get_sync_url(), target_metadata=target_metadata, literal_binds=True, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    connectable = engine_from_config({"sqlalchemy.url": _get_sync_url()}, prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

