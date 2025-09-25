from __future__ import annotations

import uuid
from datetime import datetime, date, time
from sqlalchemy.types import TypeDecorator, CHAR   # <-- required for the GUID shim
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import List
from OSSS.db.base import Base, UUIDMixin, GUID, JSONB, TimestampMixin


class User(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "users"

    __table_args__ = {
        "comment": (
            "Stores users records for the application. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "Primary key is `id`."
        )
    }

    username: Mapped[str] = mapped_column(sa.Text, unique=True, nullable=False)
    email: Mapped[str] = mapped_column(sa.Text, unique=True, nullable=False)
    userprofile: Mapped[List["UserProfile"]] = relationship(
        "UserProfile", back_populates="user", cascade="all, delete-orphan"
    )
    topic: Mapped[List["Topic"]] = relationship(
        "Topic", back_populates="user", cascade="all, delete-orphan"
    )

    studentsubmission: Mapped[List["StudentSubmission"]] = relationship(
        "StudentSubmission", back_populates="user", cascade="all, delete-orphan"
    )

    guardianinvitation: Mapped[List["GuardianInvitation"]] = relationship(
        "GuardianInvitation", back_populates="user", cascade="all, delete-orphan"
    )

    coursework: Mapped[List["CourseWork"]] = relationship(
        "CourseWork", back_populates="user", cascade="all, delete-orphan"
    )

    course: Mapped[List["Course"]] = relationship(
        "Course", back_populates="user", cascade="all, delete-orphan"
    )

    announcement: Mapped[List["Announcement"]] = relationship(
        "Announcement", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"User(id={self.id!r}, username={self.username!r})"



