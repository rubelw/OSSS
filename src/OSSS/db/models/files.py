from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB, TimestampMixin

class File(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "files"

    storage_key: Mapped[str] = mapped_column(sa.String(512), nullable=False)
    filename: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    size: Mapped[Optional[int]] = mapped_column(sa.BigInteger)
    mime_type: Mapped[Optional[str]] = mapped_column(sa.String(127))
    created_by: Mapped[Optional[str]] = mapped_column(GUID(), sa.ForeignKey("users.id"))
