from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class AttendanceDailySummary(UUIDMixin, Base):
    __tablename__ = "attendance_daily_summary"

    student_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    date: Mapped[date] = mapped_column(sa.Date, nullable=False)
    present_minutes: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default=text("0"))
    absent_minutes: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default=text("0"))
    tardy_minutes: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default=text("0"))

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)

    __table_args__ = (UniqueConstraint("student_id", "date", name="uq_attendance_daily"),)
