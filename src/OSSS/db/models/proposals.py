
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
    district_id: Mapped[Optional[str]] = mapped_column(GUID(), index=True)
    association_id: Mapped[Optional[str]] = mapped_column(GUID(), index=True)

    title: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(sa.Text)
    status: Mapped[str] = mapped_column(ProposalStatus, nullable=False, server_default="draft")
    submitted_at: Mapped[Optional[sa.DateTime]] = mapped_column(sa.DateTime(timezone=True))

    attributes = mapped_column(JSON, nullable=True)

    alignments: Mapped[List["ProposalStandardMap"]] = relationship("ProposalStandardMap", back_populates="proposal", cascade="all, delete-orphan")
    review_rounds: Mapped[List["ReviewRound"]] = relationship("ReviewRound", back_populates="proposal", cascade="all, delete-orphan")
    approvals: Mapped[List["Approval"]] = relationship("Approval", back_populates="proposal", cascade="all, delete-orphan")
    curriculum: Mapped[Optional["Curriculum"]] = relationship("Curriculum", back_populates="proposal", uselist=False, cascade="all, delete-orphan")
