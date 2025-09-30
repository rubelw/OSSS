from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional, ClassVar

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM  # only used if you want DB-level enum later

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB  # JSONB kept for cross-dialect aliasing if used elsewhere
from OSSS.db.models.enums import CourseState  # or: from .enums import CourseState


class Course(UUIDMixin, Base):
    __tablename__ = "courses"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] = (
        "owner=curriculum_instruction_assessment | division_of_schools | early_childhood_extended_programs | "
        "faith_based_religious_if_applicable | special_education_related_services | teaching_instructional_support; "
        "description=Stores courses records for the application and integrates Google Classroom metadata. "
        "Key attributes include name, code/section. "
        "References related entities via: school, subject, user. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "19 column(s) defined. "
        "Primary key is `id`. "
        "3 foreign key field(s) detected."
    )

    __table_args__ = (
        # Keep your existing uniqueness intent; extend if needed
        UniqueConstraint("school_id", "code", "section", name="uq_courses_school_code_section"),
        {
            "comment": (
                "Stores course records and Google Classroom fields. "
                "Key attributes include name, code/section. "
                "References related entities via: school, subject, user. "
                "Includes standard audit timestamps (created_at, updated_at). "
                "19 column(s) defined. Primary key is `id`. 3 foreign key field(s) detected."
            ),
            "info": {
                "note": NOTE,
                "description": (
                    "Stores course records for the application and integrates Google Classroom metadata. "
                    "Key attributes include name, code/section. "
                    "References related entities via: school, subject, user."
                ),
            },
        },
    )

    # --- OSSS (existing) fields ---
    school_id: Mapped[Any] = mapped_column(
        GUID(), ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True
    )
    subject_id: Mapped[Optional[Any]] = mapped_column(
        GUID(), ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Kept original OSSS naming:
    name: Mapped[str] = mapped_column(sa.Text, nullable=False)
    code: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)
    credit_hours: Mapped[Optional[Decimal]] = mapped_column(sa.Numeric(4, 2), nullable=True)

    # --- Google Classroom additions ---
    user_id: Mapped[Any] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    section: Mapped[Optional[str]] = mapped_column(sa.String(255), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)
    room: Mapped[Optional[str]] = mapped_column(sa.String(64), nullable=True)
    owner_id: Mapped[Optional[str]] = mapped_column(sa.String(64), nullable=True)  # Google "ownerId"
    course_state: Mapped[CourseState] = mapped_column(
        sa.Enum(CourseState, name="course_state"),  # ORM enum; consider PG ENUM migration if desired
        default=CourseState.PROVISIONED,
        nullable=False,
    )
    enrollment_code: Mapped[Optional[str]] = mapped_column(sa.String(64), nullable=True, index=True)
    alternate_link: Mapped[Optional[str]] = mapped_column(sa.String(512), nullable=True)
    calendar_id: Mapped[Optional[str]] = mapped_column(sa.String(255), nullable=True, index=True)
    creation_time: Mapped[Optional[datetime]] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    update_time: Mapped[Optional[datetime]] = mapped_column(sa.DateTime(timezone=True), nullable=True)

    # --- Audit timestamps (tz-aware, server-side defaults as in your original) ---
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False
    )

    # --- Relationships (Google Classroom domain) ---
    topics: Mapped[list["Topic"]] = relationship(
        back_populates="course", cascade="all,delete-orphan"
    )
    teachers: Mapped[list["CourseTeacher"]] = relationship(
        back_populates="course", cascade="all,delete-orphan"
    )
    students: Mapped[list["CourseStudent"]] = relationship(
        back_populates="course", cascade="all,delete-orphan"
    )
    announcements: Mapped[list["Announcement"]] = relationship(
        back_populates="course", cascade="all,delete-orphan"
    )
    coursework: Mapped[list["CourseWork"]] = relationship(
        back_populates="course", cascade="all,delete-orphan"
    )

    # Link back to the owning user (name per your snippet; adjust to "courses" if your User model expects it)
    user: Mapped["User"] = relationship("User", back_populates="course")
