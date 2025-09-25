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
from OSSS.db.base import Base, GUID, UUIDMixin, JSONB  # keep if JSONB is a cross-dialect alias; else use sa.JSON

class CourseWork(UUIDMixin, Base):
    __tablename__ = "coursework"

    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID, sa.ForeignKey("users.id", ondelete="CASCADE"),
        index=True, nullable=False
    )

    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), index=True)
    topic_id: Mapped[Optional[int]] = mapped_column(ForeignKey("topics.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    work_type: Mapped[WorkType] = mapped_column(SQLEnum(WorkType), default=WorkType.ASSIGNMENT)
    state: Mapped[PublicationState] = mapped_column(SQLEnum(PublicationState), default=PublicationState.PUBLISHED)
    due_date: Mapped[Optional[date]] = mapped_column(Date)
    due_time: Mapped[Optional[time]] = mapped_column(Time)
    max_points: Mapped[Optional[float]] = mapped_column(Float)
    creation_time: Mapped[Optional[datetime]] = mapped_column(DateTime)
    update_time: Mapped[Optional[datetime]] = mapped_column(DateTime)

    course: Mapped[Course] = relationship(back_populates="coursework")
    topic: Mapped[Optional[Topic]] = relationship()
    materials: Mapped[list["Material"]] = relationship(back_populates="coursework", cascade="all,delete-orphan")
    submissions: Mapped[list["StudentSubmission"]] = relationship(back_populates="coursework", cascade="all,delete-orphan")
    user: Mapped["User"] = relationship("User", back_populates="coursework")
