from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class AttendanceEvent(UUIDMixin, Base):
    __tablename__ = "attendance_events"

    student_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    section_meeting_id: Mapped[Optional[Any]] = mapped_column(GUID(), ForeignKey("section_meetings.id", ondelete="SET NULL"))
    date: Mapped[date] = mapped_column(sa.Date, nullable=False)
    code: Mapped[str] = mapped_column(sa.Text, ForeignKey("attendance_codes.code", ondelete="RESTRICT"), nullable=False)
    minutes: Mapped[Optional[int]] = mapped_column(sa.Integer)
    notes: Mapped[Optional[str]] = mapped_column(sa.Text)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)

    __table_args__ = (UniqueConstraint("student_id", "date", "section_meeting_id", name="uq_attendance_event"),)
