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




class Course(UUIDMixin, Base):
    __tablename__ = "courses"

    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID, sa.ForeignKey("users.id", ondelete="CASCADE"),
        index=True, nullable=False
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    section: Mapped[Optional[str]] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text)
    room: Mapped[Optional[str]] = mapped_column(String(64))
    owner_id: Mapped[Optional[str]] = mapped_column(String(64))  # Google "ownerId"
    course_state: Mapped[CourseState] = mapped_column(SQLEnum(CourseState), default=CourseState.PROVISIONED, nullable=False)
    enrollment_code: Mapped[Optional[str]] = mapped_column(String(64))
    alternate_link: Mapped[Optional[str]] = mapped_column(String(512))
    calendar_id: Mapped[Optional[str]] = mapped_column(String(255))
    creation_time: Mapped[Optional[datetime]] = mapped_column(DateTime)
    update_time: Mapped[Optional[datetime]] = mapped_column(DateTime)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # relationships
    topics: Mapped[list["Topic"]] = relationship(back_populates="course", cascade="all,delete-orphan")
    teachers: Mapped[list["CourseTeacher"]] = relationship(back_populates="course", cascade="all,delete-orphan")
    students: Mapped[list["CourseStudent"]] = relationship(back_populates="course", cascade="all,delete-orphan")
    announcements: Mapped[list["Announcement"]] = relationship(back_populates="course", cascade="all,delete-orphan")
    coursework: Mapped[list["CourseWork"]] = relationship(back_populates="course", cascade="all,delete-orphan")
    user: Mapped["User"] = relationship("User", back_populates="course")

