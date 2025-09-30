from __future__ import annotations

from typing import Optional
from datetime import datetime
import uuid

import sqlalchemy as sa
from sqlalchemy import (
    String, DateTime, Boolean, Float, ForeignKey, UniqueConstraint, Enum as SQLEnum
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, GUID, UUIDMixin
from .enums import SubmissionState


class StudentSubmission(UUIDMixin, Base):
    __tablename__ = "student_submissions"
    __table_args__ = (
        # one submission per student per coursework
        UniqueConstraint("student_user_id", "coursework_id", name="uq_student_coursework"),
    )

    # FK columns
    student_user_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )

    coursework_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("coursework.id", ondelete="CASCADE"), index=True, nullable=False
    )

    # data columns
    state: Mapped[SubmissionState] = mapped_column(
        SQLEnum(SubmissionState), default=SubmissionState.NEW, nullable=False
    )
    late: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    assigned_grade: Mapped[Optional[float]] = mapped_column(Float)
    draft_grade: Mapped[Optional[float]] = mapped_column(Float)
    alternate_link: Mapped[Optional[str]] = mapped_column(String(512))
    update_time: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # relationships
    # NOTE: `User` likely has: submissions = relationship("StudentSubmission", back_populates="user", ...)
    user: Mapped["User"] = relationship(
        "User",
        back_populates="submissions",
        foreign_keys=lambda: [StudentSubmission.student_user_id],  # defer lookup
    )

    # NOTE: ensure CourseWork model defines: submissions = relationship("StudentSubmission", back_populates="coursework", ...)
    coursework: Mapped["CourseWork"] = relationship(
        "CourseWork",
        back_populates="submissions",
        foreign_keys=lambda: [StudentSubmission.coursework_id],  # defer lookup
    )
