from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List, ClassVar

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class ClassRank(UUIDMixin, Base):
    __tablename__ = "class_ranks"
    __allow_unmapped__ = True  # helpful if you have other non-mapped attrs

    # Structured owners (optional but nicer to consume elsewhere)
    OWNERS: ClassVar[list[str]] = [
        "curriculum_instruction_assessment",
        "division_of_schools",
        "early_childhood_extended_programs",
        "faith_based_religious_if_applicable",
        "special_education_related_services",
        "student_services_school_level",
        "teaching_instructional_support",
    ]

    # Not mapped; used by exporters/docs
    NOTE: ClassVar[str] = (
            "owner=" + " | ".join(OWNERS) + "; "
                                            "description=Stores class ranks records for the application. "
                                            "References related entities via: school, student, term. "
                                            "Includes standard audit timestamps (created_at, updated_at). "
                                            "7 column(s) defined. Primary key is `id`. 3 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment": (
            "Stores class ranks records for the application. "
            "References related entities via: school, student, term. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "7 column(s) defined. Primary key is `id`. 3 foreign key field(s) detected."
        ),
        "info": {
            # your DBML exporter reads this to emit a table-level Note
            "note": NOTE,
            # optional structured metadata for other tooling:
            "owners": OWNERS,
            "description": (
                "Stores class ranks records for the application. "
                "References related entities via: school, student, term. "
                "Includes standard audit timestamps (created_at, updated_at). "
                "7 column(s) defined. Primary key is `id`. 3 foreign key field(s) detected."
            ),
        },
    }

    school_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("schools.id", ondelete="CASCADE"), nullable=False)
    term_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("academic_terms.id", ondelete="CASCADE"), nullable=False)
    student_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    rank: Mapped[int] = mapped_column(sa.Integer, nullable=False)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)

