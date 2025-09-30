from __future__ import annotations

import uuid
from typing import Optional
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import String, DateTime, Boolean, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .enums import SubmissionState
from OSSS.db.base import Base, GUID, UUIDMixin


class StudentSubmission(UUIDMixin, Base):
    __tablename__ = "student_submissions"
    __table_args__ = (
        sa.UniqueConstraint(
            "student_user_id", "coursework_id",
            name="uq_student_submission_per_coursework"
        ),
    )

    # who submitted
    student_user_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("users.id", ondelete="CASCADE"),
        index=True, nullable=False
    )

    # which coursework
    coursework_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("courseworks.id", ondelete="CASCADE"),
        index=True, nullable=False
    )

    state: Mapped[SubmissionState] = mapped_column(
        sa.Enum(SubmissionState, name="submission_state"),
        default=SubmissionState.NEW, nullable=False
    )
    late: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    assigned_grade: Mapped[Optional[float]] = mapped_column(Float)
    draft_grade: Mapped[Optional[float]] = mapped_column(Float)
    alternate_link: Mapped[Optional[str]] = mapped_column(String(512))
    update_time: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # relationships
    student: Mapped["User"] = relationship(
        "User",
        back_populates="submissions",
        foreign_keys="StudentSubmission.student_user_id",
        passive_deletes=True,
    )

    coursework: Mapped["CourseWork"] = relationship(
        "CourseWork",
        back_populates="submissions",
        foreign_keys="StudentSubmission.coursework_id",
        passive_deletes=True,
    )
