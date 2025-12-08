from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List, ClassVar

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from OSSS.db.models.enums import GradeLevels, GRADE_LEVEL_ORDINALS
from OSSS.db.base import Base, UUIDMixin, GUID, JSONB


class GradeLevel(UUIDMixin, Base):
    __tablename__ = "grade_levels"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] = (
        "owner=curriculum_instruction_assessment | division_of_schools | early_childhood_extended_programs | faith_based_religious_if_applicable | special_education_related_services | student_services_school_level | teaching_instructional_support; "
        "description=Stores grade levels records for the application. "
        "Key attributes include name. "
        "References related entities via: school. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "6 column(s) defined. "
        "Primary key is `id`. "
        "1 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment": (
            "Stores grade levels records for the application. "
            "Key attributes include name. "
            "References related entities via: school. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "6 column(s) defined. "
            "Primary key is `id`. "
            "1 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description": (
                "Stores grade levels records for the application. "
                "Key attributes include name. "
                "References related entities via: school. "
                "Includes standard audit timestamps (created_at, updated_at). "
                "6 column(s) defined. "
                "Primary key is `id`. "
                "1 foreign key field(s) detected."
            ),
        },
    }

    school_id: Mapped[Any] = mapped_column(
        GUID(), ForeignKey("schools.id", ondelete="CASCADE"), nullable=False
    )

    name: Mapped[GradeLevels] = mapped_column(
        sa.Enum(GradeLevels, name="grade_levels_enum_name"),
        nullable=False,
    )

    ordinal: Mapped[Optional[int]] = mapped_column(sa.Integer)

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

    @validates("name")
    def _set_ordinal_from_name(self, key: str, value: GradeLevels) -> GradeLevels:
        """
        Whenever name is set, also set ordinal to the canonical grade number.
        """
        # If the enum comes in as a string, coerce to GradeLevels first
        if isinstance(value, str):
            value = GradeLevels(value)

        self.ordinal = GRADE_LEVEL_ORDINALS.get(value)
        return value
