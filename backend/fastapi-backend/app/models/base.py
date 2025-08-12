from __future__ import annotations
from datetime import datetime, date
import uuid
import sqlalchemy as sa

from sqlalchemy.orm import declarative_base, declared_attr
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import MetaData, TIMESTAMP, text, DateTime
from sqlalchemy.types import TypeDecorator, CHAR

# 👇 add this guarded import near the top of the file
try:
    from sqlalchemy.dialects.postgresql import UUID as PGUUID  # native UUID
except Exception:  # e.g., running on SQLite / tests
    PGUUID = None

# --- JSONB shim -------------------------------------------------------------
try:
    from sqlalchemy.dialects.postgresql import JSONB as PGJSONB
except Exception:
    PGJSONB = None

# Export a *type class* you can instantiate: JSONBType()
JSONBType = PGJSONB if PGJSONB is not None else sa.JSON

# (optional) keep a familiar alias if you want:
JSONB = JSONBType  # so JSONB() works everywhere

# --- TSVECTOR shim ----------------------------------------------------------
try:
    from sqlalchemy.dialects.postgresql import TSVECTOR as PG_TSVECTOR
except Exception:
    PG_TSVECTOR = None

# Export a *type class* you can instantiate: TSVectorType()
TSVectorType = PG_TSVECTOR if PG_TSVECTOR is not None else sa.Text


# Naming conventions help Alembic autogenerate predictable names
convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}
metadata = MetaData(naming_convention=convention)
Base = declarative_base(metadata=metadata)

class GUID(TypeDecorator):
    """Platform-independent GUID/UUID.

    - On PostgreSQL → uses UUID (native)
    - Else (e.g., SQLite) → stores as CHAR(36)
    """
    impl = CHAR
    cache_ok = True

    @property
    def python_type(self):
        return uuid.UUID

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql" and PGUUID is not None:
            return dialect.type_descriptor(PGUUID())
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if not isinstance(value, uuid.UUID):
            value = uuid.UUID(str(value))
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        # SQLite may return bytes/memoryview
        if isinstance(value, (bytes, bytearray, memoryview)):
            value = bytes(value).decode("utf-8")
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(str(value))

# --- add this helper ---
def generate_uuid_str() -> str:
    """Generate a stringified UUID (works in all databases)."""
    return str(uuid.uuid4())

class UUIDMixin:
    """Adds an 'id' UUID primary key that works on Postgres and SQLite."""
    id: Mapped[str] = mapped_column(
        CHAR(36),
        primary_key=True,
        default=generate_uuid_str,  # Python-side default works on all DBs
        nullable=False,
    )

class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: str(uuid.uuid4()),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: str(uuid.uuid4()),
    )

def ts_columns(sa):
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), default=lambda: str(uuid.uuid4()), nullable=False),
    ]

class JSONB(TypeDecorator):
    """JSON that is JSONB on Postgres, JSON elsewhere."""
    impl = sa.JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql" and PGJSONB is not None:
            return dialect.type_descriptor(PGJSONB())
        return dialect.type_descriptor(sa.JSON())

class TSVectorType(TypeDecorator):
    """TSVECTOR on Postgres, TEXT elsewhere (e.g., SQLite for tests)."""
    impl = sa.Text
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql" and PG_TSVECTOR is not None:
            return dialect.type_descriptor(PG_TSVECTOR())
        return dialect.type_descriptor(sa.Text())