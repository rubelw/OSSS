from __future__ import annotations

import uuid
from typing import Optional, List
from datetime import datetime, date, time

import sqlalchemy as sa
from sqlalchemy import String, DateTime, Boolean, Text, ForeignKey, Date, Time, Float, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .enums import WorkType, PublicationState
from OSSS.db.base import Base, GUID, UUIDMixin


class CourseWork(UUIDMixin, Base):
    __tablename__ = "coursework"

    # who created/owns this coursework
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID, sa.ForeignKey("users.id", ondelete="CASCADE"),
        index=True, nullable=False
    )

    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), index=True, nullable=False)
    topic_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID, sa.ForeignKey("topics.id", ondelete="SET NULL"),
        index=True, nullable=True
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)

    work_type: Mapped[WorkType] = mapped_column(
        SQLEnum(WorkType, name="work_type"), default=WorkType.ASSIGNMENT, nullable=False
    )
    state: Mapped[PublicationState] = mapped_column(
        SQLEnum(PublicationState, name="publication_state"), default=PublicationState.PUBLISHED, nullable=False
    )

    due_date: Mapped[Optional[date]] = mapped_column(Date)
    due_time: Mapped[Optional[time]] = mapped_column(Time)
    max_points: Mapped[Optional[float]] = mapped_column(Float)

    creation_time: Mapped[Optional[datetime]] = mapped_column(DateTime)
    update_time: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # relationships
    course: Mapped["Course"] = relationship(
        "Course",
        back_populates="coursework",
        passive_deletes=True,
    )

    topic: Mapped[Optional["Topic"]] = relationship(
        "Topic",
        back_populates="courseworks",
        foreign_keys=[topic_id],
        passive_deletes=True,  # harmless with SET NULL
    )

    materials: Mapped[List["Material"]] = relationship(
        "Material",
        back_populates="coursework",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    submissions: Mapped[List["StudentSubmission"]] = relationship(
        "StudentSubmission",
        back_populates="coursework",
        cascade="all, delete-orphan",
        passive_deletes=True,
        foreign_keys="StudentSubmission.coursework_id",  # ensures it picks the coursework FK
    )

    user: Mapped["User"] = relationship(
        "User",
        back_populates="coursework",  # <-- make sure User has `coursework = relationship("CourseWork", back_populates="user", ...)`
        passive_deletes=True,
    )
