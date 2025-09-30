# src/OSSS/db/models/studentsubmission.py
from __future__ import annotations

from datetime import datetime
from typing import Optional
import uuid

import sqlalchemy as sa
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, GUID, UUIDMixin
from .enums import SubmissionState


class StudentSubmission(UUIDMixin, Base):
    __tablename__ = "student_submissions"

    # FKs
    student_user_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )

    # ⚠️ Make sure this table name matches CourseWork.__tablename__
    coursework_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("courseworks.id", ondelete="CASCADE"), index=True, nullable=False
    )

    # Fields
    state: Mapped[SubmissionState] = mapped_column(
        sa.Enum(SubmissionState, name="submission_state"), default=SubmissionState.NEW, nullable=False
    )
    late: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    assigned_grade: Mapped[Optional[float]] = mapped_column(Float)
    draft_grade: Mapped[Optional[float]] = mapped_column(Float)
    alternate_link: Mapped[Optional[str]] = mapped_column(String(512))
    update_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Relationships (names must match the other side's back_populates)
    student: Mapped["User"] = relationship(
        "User",
        back_populates="submissions",
        foreign_keys=[student_user_id],
        passive_deletes=True,
    )

    coursework: Mapped["CourseWork"] = relationship(
        "CourseWork",
        back_populates="submissions",
        foreign_keys=[coursework_id],
        passive_deletes=True,
    )

    __table_args__ = (
        sa.UniqueConstraint(
            "student_user_id", "coursework_id", name="uq_submission_student_coursework"
        ),
    )
