from __future__ import annotations

import uuid
from datetime import datetime, date, time
from sqlalchemy.types import TypeDecorator, CHAR   # <-- required for the GUID shim
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB, TimestampMixin


class User(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "users"

    __table_args__ = {
        "comment": (
            "Stores users records for the application. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "Primary key is `id`."
        )
    }

    username: Mapped[str] = mapped_column(sa.Text, unique=True, nullable=False)
    email: Mapped[str] = mapped_column(sa.Text, unique=True, nullable=False)

    def __repr__(self) -> str:
        return f"User(id={self.id!r}, username={self.username!r})"



