from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB, ts_cols
from typing import ClassVar


class Alignment(UUIDMixin, Base):
    __tablename__ = "alignments"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=curriculum_instruction_assessment | division_of_schools | early_childhood_extended_programs | faith_based_religious_if_applicable | special_education_related_services | teaching_instructional_support; "
        "description=Stores alignments records for the application. "
        "References related entities via: curriculum version, requirement. "
        "Includes standard audit timestamps (created_at). "
        "7 column(s) defined. "
        "Primary key is `id`. "
        "2 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment":         (
            "Stores alignments records for the application. "
            "References related entities via: curriculum version, requirement. "
            "Includes standard audit timestamps (created_at). "
            "7 column(s) defined. "
            "Primary key is `id`. "
            "2 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores alignments records for the application. "
            "References related entities via: curriculum version, requirement. "
            "Includes standard audit timestamps (created_at). "
            "7 column(s) defined. "
            "Primary key is `id`. "
            "2 foreign key field(s) detected."
        ),
        },
    }


    curriculum_version_id: Mapped = mapped_column(GUID(), sa.ForeignKey("curriculum_versions.id", ondelete="CASCADE"), nullable=False, index=True)
    requirement_id: Mapped = mapped_column(GUID(), sa.ForeignKey("requirements.id", ondelete="CASCADE"), nullable=False, index=True)

    alignment_level: Mapped[str] = mapped_column(sa.String(32), nullable=False, server_default="unknown")  # aligned|partial|not_aligned|unknown
    evidence_url: Mapped[str | None] = mapped_column(sa.String(512))
    notes: Mapped[str | None] = mapped_column(sa.Text)

    created_at, updated_at = ts_cols()

    curriculum_version = relationship("CurriculumVersion", back_populates="alignments", lazy="joined")
    requirement = relationship("Requirement", back_populates="alignments", lazy="joined")


