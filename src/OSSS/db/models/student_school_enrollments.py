from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List, ClassVar

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB
from OSSS.db.models.enums import EnrollmentStatus  # <-- NEW IMPORT


class StudentSchoolEnrollment(UUIDMixin, Base):
    __tablename__ = "student_school_enrollments"
    __allow_unmapped__ = True

    # keep NOTE out of the SQLAlchemy mapper
    NOTE: ClassVar[str] = (
        "owner=curriculum_instruction_assessment | division_of_schools | "
        "early_childhood_extended_programs | faith_based_religious_if_applicable | "
        "special_education_related_services | student_services_school_level | "
        "teaching_instructional_support; "
        "description=Stores student school enrollments records for the application. "
        "References related entities via: school, student. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "9 column(s) defined. "
        "Primary key is `id`. "
        "2 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment": (
            "Stores student school enrollments records for the application. "
            "References related entities via: school, student. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "9 column(s) defined. "
            "Primary key is `id`. "
            "2 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description": (
                "Stores student school enrollments records for the application. "
                "References related entities via: school, student. "
                "Includes standard audit timestamps (created_at, updated_at). "
                "9 column(s) defined. "
                "Primary key is `id`. "
                "2 foreign key field(s) detected."
            ),
        },
    }

    student_id: Mapped[Any] = mapped_column(
        GUID(), ForeignKey("students.id", ondelete="CASCADE"), nullable=False
    )
    school_id: Mapped[Any] = mapped_column(
        GUID(), ForeignKey("schools.id", ondelete="CASCADE"), nullable=False
    )
    entry_date: Mapped[date] = mapped_column(sa.Date, nullable=False)
    exit_date: Mapped[Optional[date]] = mapped_column(sa.Date)

    # UPDATED: use Enum + EnrollmentStatus type
    status = sa.Column(
        sa.Enum(
            "ENROLLED",
            "WITHDRAWN",
            "TRANSFERRED",
            "GRADUATED",
            "OTHER",
            name="enrollment_status",
        ),
        nullable=False,
        server_default="ENROLLED",
    )

    exit_reason: Mapped[Optional[str]] = mapped_column(sa.Text)
    grade_level_id: Mapped[Optional[Any]] = mapped_column(
        GUID(), ForeignKey("grade_levels.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
        nullable=False,
    )
