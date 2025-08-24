from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB, TimestampMixin

class HRPosition(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "hr_positions"

    title: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    department_segment_id: Mapped[Optional[str]] = mapped_column(GUID(), sa.ForeignKey("gl_segments.id", ondelete="SET NULL"))
    grade: Mapped[Optional[str]] = mapped_column(sa.String(32))
    fte: Mapped[Optional[float]] = mapped_column(sa.Numeric(5, 2))
    attributes: Mapped[Optional[dict]] = mapped_column(JSONB())

    assignments: Mapped[list["HRPositionAssignment"]] = relationship(
        "HRPositionAssignment", back_populates="position", cascade="all, delete-orphan"
    )
