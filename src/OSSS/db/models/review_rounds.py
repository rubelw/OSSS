
from __future__ import annotations

from typing import List, Optional
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, TimestampMixin, GUID


class ReviewRound(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "review_rounds"
    __table_args__ = (sa.UniqueConstraint("proposal_id", "round_no", name="uq_review_round_proposal_round"),)

    proposal_id: Mapped[str] = mapped_column(GUID(), sa.ForeignKey("proposals.id", ondelete="CASCADE"), nullable=False, index=True)
    round_no: Mapped[int] = mapped_column(sa.Integer, nullable=False)

    opened_at: Mapped[Optional[sa.DateTime]] = mapped_column(sa.DateTime(timezone=True))
    closed_at: Mapped[Optional[sa.DateTime]] = mapped_column(sa.DateTime(timezone=True))
    status: Mapped[Optional[str]] = mapped_column(sa.Enum("open", "closed", "canceled", name="review_round_status", native_enum=False), server_default="open")

    proposal = relationship("Proposal", back_populates="review_rounds")
    reviews: Mapped[List["Review"]] = relationship("Review", back_populates="round", cascade="all, delete-orphan")
    decision: Mapped[Optional["RoundDecision"]] = relationship("RoundDecision", back_populates="round", uselist=False, cascade="all, delete-orphan")
