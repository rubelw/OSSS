from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship
from OSSS.db.base import Base, UUIDMixin, GUID, JSONB, ts_cols
from typing import ClassVar


class ReviewRequest(UUIDMixin, Base):
    __tablename__ = "review_requests"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=curriculum_instruction_assessment | division_of_schools | early_childhood_extended_programs | faith_based_religious_if_applicable | special_education_related_services | teaching_instructional_support; "
        "description=Stores review requests records for the application. "
        "References related entities via: association, curriculum version. "
        "Includes standard audit timestamps (created_at). "
        "8 column(s) defined. "
        "Primary key is `id`. "
        "2 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment":         (
            "Stores review requests records for the application. "
            "References related entities via: association, curriculum version. "
            "Includes standard audit timestamps (created_at). "
            "8 column(s) defined. "
            "Primary key is `id`. "
            "2 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores review requests records for the application. "
            "References related entities via: association, curriculum version. "
            "Includes standard audit timestamps (created_at). "
            "8 column(s) defined. "
            "Primary key is `id`. "
            "2 foreign key field(s) detected."
        ),
        },
    }


    curriculum_version_id: Mapped = mapped_column(GUID(), sa.ForeignKey("curriculum_versions.id", ondelete="CASCADE"), nullable=False, index=True)
    association_id: Mapped = mapped_column(GUID(), sa.ForeignKey("education_associations.id", ondelete="CASCADE"), nullable=False, index=True)

    status: Mapped[str] = mapped_column(sa.String(32), nullable=False, server_default="submitted")  # submitted|in_review|approved|rejected
    submitted_at: Mapped[sa.DateTime | None] = mapped_column(sa.DateTime(timezone=True))
    decided_at: Mapped[sa.DateTime | None] = mapped_column(sa.DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(sa.Text)

    created_at = sa.Column(sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())
    updated_at = sa.Column(sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())

    curriculum_version = relationship("CurriculumVersion", back_populates="reviews", lazy="joined")
    association = relationship("EducationAssociation", back_populates="reviews", lazy="joined")


