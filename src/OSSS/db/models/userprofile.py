from __future__ import annotations
from typing import Optional, List
from datetime import datetime
from sqlalchemy import (
    String, Integer, DateTime, Boolean, Text, JSON, ForeignKey, Enum as SQLEnum
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
import sqlalchemy as sa
import uuid

from OSSS.db.base import Base, GUID, UUIDMixin, JSONB  # keep if JSONB is a cross-dialect alias; else use sa.JSON

class UserProfile(UUIDMixin, Base):
    __tablename__ = "user_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID, sa.ForeignKey("users.id", ondelete="CASCADE"),
        index=True, nullable=False
    )

    primary_email: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    full_name: Mapped[Optional[str]] = mapped_column(String(255))
    photo_url: Mapped[Optional[str]] = mapped_column(String(512))
    is_teacher: Mapped[bool] = mapped_column(Boolean, default=False)
    is_student: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # relationships
    teaching_assignments: Mapped[list["CourseTeacher"]] = relationship(back_populates="teacher", cascade="all,delete-orphan")
    enrollments: Mapped[list["CourseStudent"]] = relationship(back_populates="student", cascade="all,delete-orphan")
    user: Mapped["User"] = relationship("User", back_populates="userprofile")
