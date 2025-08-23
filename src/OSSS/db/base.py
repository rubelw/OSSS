# src/OSSS/db/base.py
from __future__ import annotations

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import MetaData
from sqlalchemy.dialects import postgresql as pg
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import CHAR, JSON, TypeDecorator, TEXT

# -----------------------------------------------------------------------------
# Optional TSVectorType
# -----------------------------------------------------------------------------
try:
    # Preferred: provides richer features (weights, indexes, etc.)
    from sqlalchemy_utils import TSVectorType as _SAU_TSVectorType  # type: ignore
    TSVectorType = _SAU_TSVectorType  # re-export
except Exception:  # pragma: no cover
    # Fallback: minimal type that maps to TSVECTOR on PG, TEXT elsewhere
    class TSVectorType(TypeDecorator):
        impl = TEXT
        cache_ok = True

        def load_dialect_impl(self, dialect):
            if dialect.name == "postgresql":
                return dialect.type_descriptor(pg.TSVECTOR())
            return dialect.type_descriptor(TEXT())


# -----------------------------------------------------------------------------
# Declarative Base with naming conventions (great for Alembic autogenerate)
# -----------------------------------------------------------------------------
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


# -----------------------------------------------------------------------------
# GUID type that works on both Postgres and SQLite
# -----------------------------------------------------------------------------
class GUID(TypeDecorator):
    """
    Platform-independent UUID type.

    - On PostgreSQL ⇒ uses UUID(as_uuid=True)
    - Elsewhere     ⇒ stores as CHAR(36)

    Returns/accepts Python uuid.UUID objects in both cases.
    """
    impl = CHAR(36)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(pg.UUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql":
            return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
        return str(value if isinstance(value, uuid.UUID) else uuid.UUID(str(value)))

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


# -----------------------------------------------------------------------------
# JSONB that becomes JSONB on Postgres and JSON elsewhere
# -----------------------------------------------------------------------------
class JSONB(TypeDecorator):
    """
    Platform-aware JSON type.

    - On PostgreSQL ⇒ JSONB
    - Elsewhere     ⇒ JSON
    """
    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(pg.JSONB())
        return dialect.type_descriptor(JSON())


# -----------------------------------------------------------------------------
# Common mixin with UUID PK + timestamps
# -----------------------------------------------------------------------------
class UUIDMixin:
    """
    Mixin that adds:
      - id: UUID primary key (GUID)
      - created_at: timezone-aware timestamp, defaults to NOW() on DB
      - updated_at: timezone-aware timestamp, defaults to NOW(), auto-updates
    """
    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)

    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
        nullable=False,
    )


__all__ = ["Base", "UUIDMixin", "GUID", "JSONB", "TSVectorType"]

