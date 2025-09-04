from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List, ClassVar

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class AttendanceCode(Base):
    __tablename__ = "attendance_codes"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=curriculum_instruction_assessment | division_of_schools | early_childhood_extended_programs | faith_based_religious_if_applicable | special_education_related_services | student_services_school_level | teaching_instructional_support; "
        "description=Stores attendance codes records for the application. "
        "Key attributes include code. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "6 column(s) defined."
    )

    __table_args__ = {
        "comment":         (
            "Stores attendance codes records for the application. "
            "Key attributes include code. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "6 column(s) defined."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores attendance codes records for the application. "
            "Key attributes include code. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "6 column(s) defined."
        ),
        },
    }


    code: Mapped[str] = mapped_column(sa.Text, primary_key=True)
    description: Mapped[Optional[str]] = mapped_column(sa.Text)
    is_present: Mapped[bool] = mapped_column(sa.Text, nullable=False, server_default=text("0"))
    is_excused: Mapped[bool] = mapped_column(sa.Text, nullable=False, server_default=text("0"))

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)


