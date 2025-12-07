# src/OSSS/db/models/proposals.py
from __future__ import annotations

import uuid
from typing import Optional, List
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship, synonym

from OSSS.db.models.associations import proposal_standard_map
from OSSS.db.base import Base, UUIDMixin, TimestampMixin, GUID, JSON

ProposalStatus = sa.Enum(
    "draft", "submitted", "in_review", "approved", "rejected",
    name="proposal_status",
    native_enum=False,
)

class Proposal(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "proposals"

    organization_id: Mapped[Optional[str]] = mapped_column(GUID(), index=True)
    association_id: Mapped[Optional[str]]  = mapped_column(GUID(), index=True)

    committee_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        sa.ForeignKey("committees.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    submitted_by_id = sa.Column(GUID(), sa.ForeignKey("persons.id",  ondelete="SET NULL"))
    school_id       = sa.Column(GUID(), sa.ForeignKey("schools.id",  ondelete="SET NULL"))
    subject_id      = sa.Column(GUID(), sa.ForeignKey("subjects.id", ondelete="SET NULL"))
    course_id       = sa.Column(GUID(), sa.ForeignKey("courses.id",  ondelete="SET NULL"))

    title: Mapped[str]             = mapped_column(sa.String(255), nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(sa.Text)
    rationale                      = sa.Column(sa.Text)

    status: Mapped[str] = mapped_column(
        ProposalStatus, nullable=False, server_default="draft"
    )
    submitted_at: Mapped[Optional[sa.DateTime]] = mapped_column(sa.DateTime(timezone=True))
    attributes = mapped_column(JSON, nullable=True)

    created_at = sa.Column(sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())
    updated_at = sa.Column(sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())

    # NO curriculum_id column here anymore

    committee: Mapped["Committee"] = relationship(
        "Committee",
        back_populates="proposals",
    )

    alignments: Mapped[List["Standard"]] = relationship(
        "Standard",
        secondary=proposal_standard_map,
        back_populates="proposals",
        lazy="selectin",
        overlaps="standards,alignments",
    )

    standards: Mapped[List["Standard"]] = relationship(
        "Standard",
        secondary=proposal_standard_map,
        back_populates="proposals",
        lazy="selectin",
        overlaps="alignments,standards",
    )

    review_rounds: Mapped[List["ReviewRound"]] = relationship(
        "ReviewRound",
        back_populates="proposal",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
    )

    approvals: Mapped[List["Approval"]] = relationship(
        "Approval",
        back_populates="proposal",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
    )

    documents = relationship(
        "ProposalDocument",
        back_populates="proposal",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
    )

    reviews: Mapped[List["ProposalReview"]] = relationship(
        "ProposalReview",
        back_populates="proposal",
        foreign_keys="ProposalReview.proposal_id",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
    )

    proposal_reviews = synonym("reviews")
