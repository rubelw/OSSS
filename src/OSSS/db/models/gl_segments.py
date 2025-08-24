from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB, TimestampMixin

class GLSegment(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "gl_segments"

    code: Mapped[str] = mapped_column(sa.String(32), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    seq: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    length: Mapped[Optional[int]] = mapped_column(sa.Integer)
    required: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=sa.text("true"))

    values: Mapped[list["GLSegmentValue"]] = relationship(
        "GLSegmentValue", back_populates="segment", cascade="all, delete-orphan"
    )
