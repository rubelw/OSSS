from __future__ import annotations

import uuid
from typing import Any, Optional
from decimal import Decimal
from datetime import datetime, date, time
from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List
from sqlalchemy.types import TypeDecorator, CHAR   # <-- required for the GUID shim

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB, TimestampMixin

class GUID(TypeDecorator):
    note: str = 'owner=division_of_technology_data; description=Stores users records for the application. Includes standard audit timestamps (created_at, updated_at). 5 column(s) defined. Primary key is `id`.'

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if not isinstance(value, uuid.UUID):
            value = uuid.UUID(str(value))
        # Postgres can take UUID objects, others need string
        return value if dialect.name == "postgresql" else str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))

class User(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "users"

    __table_args__ = {'comment': 'Stores users records for the application. Includes standard audit timestamps (created_at, updated_at). 5 column(s) defined. Primary key is `id`.', 'info': {'description': 'Stores users records for the application. Includes standard audit timestamps (created_at, updated_at). 5 column(s) defined. Primary key is `id`.'}}

    username: Mapped[str] = mapped_column(sa.Text, unique=True, nullable=False)
    email: Mapped[str] = mapped_column(sa.Text, unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"User(id={self.id!r}, username={self.username!r})"



