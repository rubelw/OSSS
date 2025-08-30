
from __future__ import annotations

from typing import Optional, Dict, Any
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, TimestampMixin, GUID, JSON


class Review(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "reviews"
    __table_args__ = (sa.UniqueConstraint("review_round_id", "reviewer_id", name="uq_review_round_reviewer"),)

    review_round_id: Mapped[str] = mapped_column(GUID(), sa.ForeignKey("review_rounds.id", ondelete="CASCADE"), nullable=False, index=True)
    reviewer_id: Mapped[str] = mapped_column(GUID(), sa.ForeignKey("reviewers.id", ondelete="CASCADE"), nullable=False, index=True)

    status: Mapped[str] = mapped_column(sa.Enum("draft", "submitted", name="review_status", native_enum=False), nullable=False, server_default="draft")
    submitted_at: Mapped[Optional[sa.DateTime]] = mapped_column(sa.DateTime(timezone=True))
    content: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)

    round = relationship("ReviewRound", back_populates="reviews")
    reviewer = relationship("Reviewer", back_populates="reviews")
