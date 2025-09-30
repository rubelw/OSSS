from __future__ import annotations

from datetime import datetime
from typing import Optional
import uuid

import sqlalchemy as sa
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, GUID, UUIDMixin
from .enums import SubmissionState


class StudentSubmission(UUIDMixin, Base):
    __tablename__ = "student_submissions"

    # FK to users.id
    student_user_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )

    # FK to courseworks.id  (make sure CourseWork.__tablename__ == "courseworks")
    coursework_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("courseworks.id", ondelete="CASCADE"), index=True, nullable=False
    )

    state: Mapped[SubmissionState] = mapped_column(
        SQLEnum(SubmissionState, name="submission_state"),
        default=SubmissionState.NEW,
        nullable=False,
    )
    late: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    assigned_grade: Mapped[Optional[float]] = mapped_column(Float)
    draft_grade: Mapped[Optional[float]] = mapped_column(Float)
    alternate_link: Mapped[Optional[str]] = mapped_column(String(512))
    update_time: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Relationships
    student: Mapped["User"] = relationship(
        "User",
        back_populates="submissions",
        foreign_keys=[student_user_id],
    )

    coursework: Mapped["CourseWork"] = relationship(
        "CourseWork",
        back_populates="submissions",
        foreign_keys=[coursework_id],
    )
