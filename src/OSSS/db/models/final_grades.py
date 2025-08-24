from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class FinalGrade(UUIDMixin, Base):
    __tablename__ = "final_grades"

    student_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    section_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("course_sections.id", ondelete="CASCADE"), nullable=False)
    grading_period_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("grading_periods.id", ondelete="CASCADE"), nullable=False)
    numeric_grade: Mapped[Optional[Decimal]] = mapped_column(sa.Numeric(6, 3))
    letter_grade: Mapped[Optional[str]] = mapped_column(sa.Text)
    credits_earned: Mapped[Optional[Decimal]] = mapped_column(sa.Numeric(5, 2))

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)

    __table_args__ = (UniqueConstraint("student_id", "section_id", "grading_period_id", name="uq_final_grade_period"),)
