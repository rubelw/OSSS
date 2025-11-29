from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship
from OSSS.db.base import Base, UUIDMixin, GUID, JSONB, ts_cols
from typing import ClassVar


class CurriculumVersion(UUIDMixin, Base):
    __tablename__ = "curriculum_versions"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=curriculum_instruction_assessment | division_of_schools | early_childhood_extended_programs | faith_based_religious_if_applicable | special_education_related_services | teaching_instructional_support; "
        "description=Stores curriculum versions records for the application. "
        "References related entities via: curriculum. "
        "Includes standard audit timestamps (created_at). "
        "8 column(s) defined. "
        "Primary key is `id`. "
        "1 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment":         (
            "Stores curriculum versions records for the application. "
            "References related entities via: curriculum. "
            "Includes standard audit timestamps (created_at). "
            "8 column(s) defined. "
            "Primary key is `id`. "
            "1 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores curriculum versions records for the application. "
            "References related entities via: curriculum. "
            "Includes standard audit timestamps (created_at). "
            "8 column(s) defined. "
            "Primary key is `id`. "
            "1 foreign key field(s) detected."
        ),
        },
    }


    curriculum_id: Mapped = mapped_column(GUID(), sa.ForeignKey("curricula.id", ondelete="CASCADE"), nullable=False, index=True)
    version: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    status: Mapped[str] = mapped_column(sa.String(32), nullable=False, server_default="draft")  # draft|submitted|approved|rejected
    submitted_at: Mapped[sa.DateTime | None] = mapped_column(sa.DateTime(timezone=True))
    decided_at: Mapped[sa.DateTime | None] = mapped_column(sa.DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(sa.Text)

    created_at = sa.Column(sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())
    updated_at = sa.Column(sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())

    curriculum: Mapped["Curriculum"] = relationship(
        "Curriculum", back_populates="versions", lazy="joined",
        foreign_keys="CurriculumVersion.curriculum_id",
    )
    reviews = relationship("ReviewRequest", back_populates="curriculum_version", cascade="all, delete-orphan")
    alignments = relationship("Alignment", back_populates="curriculum_version", cascade="all, delete-orphan")


