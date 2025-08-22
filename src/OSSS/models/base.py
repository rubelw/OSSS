# src/OSSS/models/base.py
from __future__ import annotations
import uuid
from datetime import datetime
import sqlalchemy as sa
from sqlalchemy.orm import declarative_base, Mapped, mapped_column
from sqlalchemy import MetaData
from sqlalchemy.types import TypeDecorator, CHAR

# --- Dialect shims ----------------------------------------------------------
try:
    from sqlalchemy.dialects.postgresql import UUID as PGUUID
except Exception:
    PGUUID = None

try:
    from sqlalchemy.dialects.postgresql import JSONB as PGJSONB
except Exception:
    PGJSONB = None

try:
    from sqlalchemy.dialects.postgresql import TSVECTOR as PG_TSVECTOR  # raw dialect type
except Exception:
    PG_TSVECTOR = None

# Export a JSONB type class you can instantiate as JSONB()
JSONB = PGJSONB if PGJSONB is not None else sa.JSON

# If you ever need the raw dialect TSVECTOR, use this name (not TSVectorType)
TSVECTOR = PG_TSVECTOR if PG_TSVECTOR is not None else sa.Text

# Naming conventions for Alembic
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
        return str(value if isinstance(value, uuid.UUID) else uuid.UUID(str(value)))

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, (bytes, bytearray, memoryview)):
            value = bytes(value).decode("utf-8")
        return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))

def generate_uuid_str() -> str:
    return str(uuid.uuid4())

class UUIDMixin:
    id: Mapped[str] = mapped_column(CHAR(36), primary_key=True, default=generate_uuid_str, nullable=False)

class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)

class TSVectorType(TypeDecorator):
    """Use Postgres TSVECTOR when available; fall back to TEXT elsewhere."""
    impl = sa.Text
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql" and PG_TSVECTOR is not None:
            return dialect.type_descriptor(PG_TSVECTOR())
        return dialect.type_descriptor(sa.Text())
