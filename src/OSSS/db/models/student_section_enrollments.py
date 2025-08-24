from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class StudentSectionEnrollment(UUIDMixin, Base):
    __tablename__ = "student_section_enrollments"

    student_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    section_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("course_sections.id", ondelete="CASCADE"), nullable=False)
    added_on: Mapped[date] = mapped_column(sa.Date, nullable=False)
    dropped_on: Mapped[Optional[date]] = mapped_column(sa.Date)
    seat_time_minutes: Mapped[Optional[int]] = mapped_column(sa.Integer)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)

    __table_args__ = (UniqueConstraint("student_id", "section_id", name="uq_student_section"),)
