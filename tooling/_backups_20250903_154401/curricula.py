from __future__ import annotations

import sqlalchemy as sa
from typing import Optional
from sqlalchemy.orm import Mapped, mapped_column, relationship
from OSSS.db.base import Base, UUIDMixin, GUID, JSONB, ts_cols, JSON


class Curriculum(UUIDMixin, Base):
    __tablename__ = "curricula"

    organization_id: Mapped = mapped_column(
        GUID(), sa.ForeignKey("organizations.id", ondelete="CASCADE"),
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
    created_at, updated_at = ts_cols()

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
        back_populates="resulting_curriculum",  # matches Proposal.resulting_curriculum above
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
