
from __future__ import annotations

from typing import Optional, List, Dict, Any
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, TimestampMixin, GUID, JSON


ProposalStatus = sa.Enum(
    "draft", "submitted", "in_review", "approved", "rejected", name="proposal_status",
    native_enum=False
)


class Proposal(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "proposals"

    # Use bare GUID columns for cross-system IDs to remain DB-agnostic without external FK requirements.
    organization_id: Mapped[Optional[str]] = mapped_column(GUID(), index=True)
    association_id: Mapped[Optional[str]] = mapped_column(GUID(), index=True)

    title: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(sa.Text)
    status: Mapped[str] = mapped_column(ProposalStatus, nullable=False, server_default="draft")
    submitted_at: Mapped[Optional[sa.DateTime]] = mapped_column(sa.DateTime(timezone=True))

    attributes = mapped_column(JSON, nullable=True)

    # If you want the inverse of Curriculum.proposal (the single proposal chosen to become a curriculum),
    # keep this; otherwise you can omit both sides of this pair.
    resulting_curriculum: Mapped[Optional["Curriculum"]] = relationship(
        "Curriculum",
        back_populates="proposal",
        foreign_keys="Curriculum.proposal_id",
        uselist=False,
        viewonly=True,  # optional: this makes it read-only; drop if you want a writable link
    )

    alignments: Mapped[List["ProposalStandardMap"]] = relationship(
        "ProposalStandardMap", back_populates="proposal", cascade="all, delete-orphan"
    )
    review_rounds: Mapped[List["ReviewRound"]] = relationship(
        "ReviewRound", back_populates="proposal", cascade="all, delete-orphan"
    )
    approvals: Mapped[List["Approval"]] = relationship(
        "Approval", back_populates="proposal", cascade="all, delete-orphan"
    )

    # This FK points FROM proposals TO curricula
    curriculum_id: Mapped[Optional[str]] = mapped_column(
        GUID(),
        sa.ForeignKey("curricula.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )

    # ← many-to-one (each proposal references zero/one curriculum)
    curriculum: Mapped[Optional["Curriculum"]] = relationship(
        "Curriculum",
        back_populates="proposals",
        foreign_keys="Proposal.curriculum_id",
        lazy="joined",
    )