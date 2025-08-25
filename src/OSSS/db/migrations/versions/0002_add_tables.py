"""Create tables for all ORM models

Revision ID: 0002_add_table
Revises: 0001_init
Create Date: 2025-08-11
"""
from __future__ import annotations

import logging
import pkgutil
from importlib import import_module
from typing import Iterable
from sqlalchemy.dialects import postgresql as psql

from alembic import op
import sqlalchemy as sa

log = logging.getLogger(__name__)

# ---- Alembic identifiers ----
revision = "0002_add_tables"
down_revision = "0001_init"
branch_labels = None
depends_on = None


# ---- Optional shims if your models reference these types ----
try:
    # Prefer your app-provided types if available
    from app.models.base import GUID, JSONB, TSVectorType  # noqa: F401
except Exception:  # pragma: no cover
    import uuid
    from sqlalchemy.types import TypeDecorator, CHAR

    class GUID(TypeDecorator):
        impl = CHAR
        cache_ok = True

        def load_dialect_impl(self, dialect):
            if dialect.name == "postgresql":
                from sqlalchemy.dialects.postgresql import UUID as PGUUID
                return dialect.type_descriptor(PGUUID(as_uuid=True))
            return dialect.type_descriptor(sa.CHAR(36))

        def process_bind_param(self, value, dialect):
            if value is None:
                return None
            if not isinstance(value, uuid.UUID):
                value = uuid.UUID(str(value))
            return str(value)

        def process_result_value(self, value, dialect):
            return None if value is None else uuid.UUID(value)

    try:
        from sqlalchemy.dialects.postgresql import JSONB as PGJSONB
    except Exception:
        PGJSONB = None

    class JSONB(TypeDecorator):
        impl = sa.JSON
        cache_ok = True

        def load_dialect_impl(self, dialect):
            if dialect.name == "postgresql" and PGJSONB is not None:
                return dialect.type_descriptor(PGJSONB())
            return dialect.type_descriptor(sa.JSON())

    try:
        from sqlalchemy.dialects.postgresql import TSVECTOR as PG_TSVECTOR

        class TSVectorType(PG_TSVECTOR):  # noqa: N801
            pass
    except Exception:
        class TSVectorType(sa.Text):  # type: ignore  # noqa: N801
            pass


# ---- Utilities ----
def _import_models():
    # Import the models package to populate Base.metadata,
    # but DO NOT import OSSS.db (which pulls in session/engine).
    import_module("OSSS.db.models")

def _ensure_users_id_is_uuid():
    bind = op.get_bind()
    insp = sa.inspect(bind)

    # If users table doesn't exist yet, nothing to do.
    if "users" not in insp.get_table_names():
        return

    # Detect current type of users.id
    cols = insp.get_columns("users")
    id_col = next((c for c in cols if c["name"] == "id"), None)
    if not id_col:
        return

    # Already UUID? then we're good.
    if isinstance(id_col["type"], psql.UUID):
        return

    # Try a straight cast first
    try:
        op.alter_column(
            "users",
            "id",
            type_=psql.UUID(as_uuid=True),
            postgresql_using="id::uuid",
            existing_nullable=False,
        )
    except Exception:
        # Fallback: swap column to a fresh UUID PK (handles non-UUID dev data)
        op.add_column(
            "users",
            sa.Column(
                "id_uuid",
                psql.UUID(as_uuid=True),
                server_default=sa.text("gen_random_uuid()"),
                nullable=False,
            ),
        )
        # If you need to preserve old IDs somewhere, COPY them to a new column before dropping.
        op.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS users_pkey")
        op.execute("ALTER TABLE users ADD PRIMARY KEY (id_uuid)")
        op.drop_column("users", "id")
        op.execute('ALTER TABLE users RENAME COLUMN id_uuid TO id')

# ---- Migration steps ----
def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")

    # Make sure users.id is UUID so FKs can reference it
    _ensure_users_id_is_uuid()

    _import_models()
    from OSSS.db.base import Base
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    # Import models so Base.metadata knows about all tables to drop
    _import_models()
    from OSSS.db.base import Base

    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)

    if bind.dialect.name == "postgresql":
        op.execute("DROP EXTENSION IF EXISTS pgcrypto;")
