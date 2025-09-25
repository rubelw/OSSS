from __future__ import annotations
from typing import Optional, List
from datetime import datetime
from sqlalchemy import (
    String, Integer, DateTime, Boolean, Text, JSON, ForeignKey, Enum as SQLEnum
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship


from OSSS.db.base import Base, UUIDMixin, JSONB  # keep if JSONB is a cross-dialect alias; else use sa.JSON

class CourseStudent(UUIDMixin, Base):
    __tablename__ = "course_students"

    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user_profiles.id", ondelete="CASCADE"), index=True)

    course: Mapped[Course] = relationship(back_populates="students")
    student: Mapped[UserProfile] = relationship(back_populates="enrollments")

    __table_args__ = (UniqueConstraint("course_id", "user_id", name="uq_student_course_user"),)
