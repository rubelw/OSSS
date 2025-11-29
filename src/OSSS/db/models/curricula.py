from __future__ import annotations

import sqlalchemy as sa
from typing import Optional, ClassVar
from sqlalchemy.orm import Mapped, mapped_column, relationship
from OSSS.db.base import Base, UUIDMixin, GUID, JSONB, ts_cols, JSON


class Curriculum(UUIDMixin, Base):
    __tablename__ = "curricula"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=teaching_instructional_support; "
        "description=Stores curricula records for the application. "
        "Key attributes include title, name. "
        "References related entities via: organization, proposal. "
        "Includes standard audit timestamps (created_at, published_at). "
        "13 column(s) defined. "
        "Primary key is `id`. "
        "2 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment":         (
            "Stores curricula records for the application. "
            "Key attributes include title, name. "
            "References related entities via: organization, proposal. "
            "Includes standard audit timestamps (created_at, published_at). "
            "13 column(s) defined. "
            "Primary key is `id`. "
            "2 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores curricula records for the application. "
            "Key attributes include title, name. "
            "References related entities via: organization, proposal. "
            "Includes standard audit timestamps (created_at, published_at). "
            "13 column(s) defined. "
            "Primary key is `id`. "
            "2 foreign key field(s) detected."
        ),
        },
    }


    organization_id: Mapped = mapped_column(
        GUID(), sa.ForeignKey("mentors.id", ondelete="CASCADE"),
        nullable=False, index=True
    )

    # This FK points FROM curricula TO proposals (the selected/approved proposal)
    proposal_id: Mapped[Optional[str]] = mapped_column(
        GUID(), sa.ForeignKey("proposals.id", ondelete="SET NULL"),
        index=True, nullable=True
    )

    title: Mapped[str] = mapped_column(sa.String(255), nullable=False, index=True)
    subject: Mapped[Optional[str]] = mapped_column(sa.String(128))
    grade_range: Mapped[Optional[str]] = mapped_column(sa.String(64))
    description: Mapped[Optional[str]] = mapped_column(sa.Text)
    attributes: Mapped[Optional[dict]] = mapped_column(sa.JSON, nullable=True)
    created_at = sa.Column(sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())
    updated_at = sa.Column(sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())



    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        sa.Enum("draft", "adopted", "retired", name="curriculum_status", native_enum=False),
        nullable=False, server_default="draft"
    )
    published_at: Mapped[Optional[sa.DateTime]] = mapped_column(sa.DateTime(timezone=True))
    metadata_json = mapped_column("metadata", JSON, nullable=True)

    # --- relationships ---

    organization = relationship("Organization", back_populates="curricula", lazy="joined")

    # one Curriculum has many Versions — keep only ONE definition; use back_populates="curriculum"
    versions: Mapped[list["CurriculumVersion"]] = relationship(
        "CurriculumVersion",
        back_populates="curriculum",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    # one Curriculum has many Units
    units: Mapped[list["CurriculumUnit"]] = relationship(
        "CurriculumUnit",
        back_populates="curriculum",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    # one Curriculum is linked to zero/one Proposal that birthed it (via curriculum.proposal_id)
    proposal: Mapped[Optional["Proposal"]] = relationship(
        "Proposal",
        back_populates="curriculum",  # matches Proposal.resulting_curriculum above
        foreign_keys="Curriculum.proposal_id",
        uselist=False,
        lazy="joined",
    )

    # one Curriculum is referenced by many Proposals (via Proposal.curriculum_id)
    proposals: Mapped[list["Proposal"]] = relationship(
        "Proposal",
        back_populates="curriculum",
        foreign_keys="Proposal.curriculum_id",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


