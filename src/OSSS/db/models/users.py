from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, TimestampMixin


class User(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "users"

    __table_args__ = {
        "comment": (
            "Stores users records for the application. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "Primary key is `id`."
        )
    }

    username: Mapped[str] = mapped_column(sa.Text, unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(sa.Text, unique=True, nullable=False, index=True)

    # --- One-to-manys to other models ---
    userprofile: Mapped[list["UserProfile"]] = relationship(
        "UserProfile", back_populates="user", cascade="all, delete-orphan"
    )
    topic: Mapped[list["Topic"]] = relationship(
        "Topic", back_populates="user", cascade="all, delete-orphan"
    )
    guardianinvitation: Mapped[list["GuardianInvitation"]] = relationship(
        "GuardianInvitation", back_populates="user", cascade="all, delete-orphan"
    )
    coursework: Mapped[list["CourseWork"]] = relationship(
        "CourseWork", back_populates="user", cascade="all, delete-orphan"
    )
    course: Mapped[list["Course"]] = relationship(
        "Course", back_populates="user", cascade="all, delete-orphan"
    )
    announcement: Mapped[list["Announcement"]] = relationship(
        "Announcement", back_populates="user", cascade="all, delete-orphan"
    )

    # --- Reverse side of StudentSubmission.student ---
    submissions: Mapped[list["StudentSubmission"]] = relationship(
        "StudentSubmission",
        back_populates="student",
        foreign_keys="StudentSubmission.student_user_id",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"User(id={self.id!r}, username={self.username!r})"
