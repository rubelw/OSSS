from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class CourseSection(UUIDMixin, Base):
    __tablename__ = "course_sections"

    course_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    term_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("academic_terms.id", ondelete="CASCADE"), nullable=False)
    section_number: Mapped[str] = mapped_column(sa.Text, nullable=False)
    capacity: Mapped[Optional[int]] = mapped_column(sa.Integer)
    school_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)

    __table_args__ = (UniqueConstraint("course_id", "term_id", "section_number", name="uq_course_term_section"),)
