from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB, TimestampMixin

class Organization(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(sa.String(255), unique=True, nullable=False)
    code: Mapped[Optional[str]] = mapped_column(sa.Text, unique=True)
    bodies: Mapped[list["Body"]] = relationship(
        "Body",
        back_populates="organization",
        cascade="all, delete-orphan",
    )
