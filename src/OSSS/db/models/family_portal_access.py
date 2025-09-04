# OSSS/db/models/family_portal_access.py
from __future__ import annotations
from datetime import datetime
import sqlalchemy as sa
from sqlalchemy import ForeignKey, text
from sqlalchemy.orm import Mapped, mapped_column
from OSSS.db.base import Base, GUID
from typing import ClassVar

class FamilyPortalAccess(Base):
    __tablename__ = "family_portal_access"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=curriculum_instruction_assessment | division_of_schools | early_childhood_extended_programs | faith_based_religious_if_applicable | special_education_related_services | student_services_school_level | teaching_instructional_support; "
        "description=Stores family portal access records for the application. "
        "References related entities via: guardian, student. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "6 column(s) defined. "
        "Primary key is `id`. "
        "2 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment":         (
            "Stores family portal access records for the application. "
            "References related entities via: guardian, student. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "6 column(s) defined. "
            "Primary key is `id`. "
            "2 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores family portal access records for the application. "
            "References related entities via: guardian, student. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "6 column(s) defined. "
            "Primary key is `id`. "
            "2 foreign key field(s) detected."
        ),
        },
    }


    id: Mapped[str] = mapped_column(
        GUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")
    )

    guardian_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("guardians.id", ondelete="CASCADE"), nullable=False, index=True
    )
    student_id: Mapped[str] = mapped_column(
        GUID(), ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True
    )
    permissions: Mapped[str | None] = mapped_column(sa.Text)

    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False
    )
