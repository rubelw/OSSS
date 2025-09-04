
from __future__ import annotations

from typing import Optional
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, TimestampMixin, GUID


class RoundDecision(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "round_decisions"

    review_round_id: Mapped[str] = mapped_column(GUID(), sa.ForeignKey("review_rounds.id", ondelete="CASCADE"), nullable=False, index=True)
    decision: Mapped[str] = mapped_column(sa.Enum(
        "approved", "approved_with_conditions", "revisions_requested", "rejected",
        name="round_decision", native_enum=False
    ), nullable=False)
    decided_at: Mapped[Optional[sa.DateTime]] = mapped_column(sa.DateTime(timezone=True))
    notes: Mapped[Optional[str]] = mapped_column(sa.Text)

    round = relationship("ReviewRound", back_populates="decision")
