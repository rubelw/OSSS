from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class TranscriptLine(UUIDMixin, Base):
    __tablename__ = "transcript_lines"

    student_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    course_id: Mapped[Optional[Any]] = mapped_column(GUID(), ForeignKey("courses.id", ondelete="SET NULL"))
    term_id: Mapped[Optional[Any]] = mapped_column(GUID(), ForeignKey("academic_terms.id", ondelete="SET NULL"))
    credits_attempted: Mapped[Optional[Decimal]] = mapped_column(sa.Numeric(5, 2))
    credits_earned: Mapped[Optional[Decimal]] = mapped_column(sa.Numeric(5, 2))
    final_letter: Mapped[Optional[str]] = mapped_column(sa.Text)
    final_numeric: Mapped[Optional[Decimal]] = mapped_column(sa.Numeric(6, 3))

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)
