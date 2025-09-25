from __future__ import annotations
from typing import Optional, List
from datetime import datetime
from sqlalchemy import (
    String, Integer, DateTime, Boolean, Text, JSON, ForeignKey, Enum as SQLEnum
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .enums import *
import sqlalchemy as sa
import uuid
from OSSS.db.base import Base,GUID, UUIDMixin, JSONB  # keep if JSONB is a cross-dialect alias; else use sa.JSON

class StudentSubmission(UUIDMixin, Base):
    __tablename__ = "student_submissions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID, sa.ForeignKey("users.id", ondelete="CASCADE"),
        index=True, nullable=False
    )

    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), index=True)
    coursework_id: Mapped[int] = mapped_column(ForeignKey("coursework.id", ondelete="CASCADE"), index=True)
    state: Mapped[SubmissionState] = mapped_column(SQLEnum(SubmissionState), default=SubmissionState.NEW)
    late: Mapped[bool] = mapped_column(Boolean, default=False)
    assigned_grade: Mapped[Optional[float]] = mapped_column(Float)
    draft_grade: Mapped[Optional[float]] = mapped_column(Float)
    alternate_link: Mapped[Optional[str]] = mapped_column(String(512))
    update_time: Mapped[Optional[datetime]] = mapped_column(DateTime)

    coursework: Mapped[CourseWork] = relationship(back_populates="submissions")
    student: Mapped[UserProfile] = relationship()

    user: Mapped[List["User"]] = relationship(
        "User", back_populates="studentsubmission", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("coursework_id", "user_id", name="uq_submission_coursework_user"),
    )
