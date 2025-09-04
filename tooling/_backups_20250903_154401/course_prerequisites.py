from __future__ import annotations

from datetime import datetime
import sqlalchemy as sa
from sqlalchemy import ForeignKey, text
from sqlalchemy.orm import Mapped, mapped_column
from OSSS.db.base import Base, GUID

class CoursePrerequisite(Base):
    __tablename__ = "course_prerequisites"

    id: Mapped[str] = mapped_column(GUID(), primary_key=True, server_default=sa.text("gen_random_uuid()"))

    course_id: Mapped[str] = mapped_column(GUID(), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    prereq_course_id: Mapped[str] = mapped_column(GUID(), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)

        sa.UniqueConstraint("course_id", "prereq_course_id", name="uq_course_prerequisites_pair"),
        sa.CheckConstraint("course_id <> prereq_course_id", name="ck_course_prereq_not_self"),
    )
