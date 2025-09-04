# src/OSSS/db/models/proposal_reviews.py
from __future__ import annotations

from datetime import datetime
from typing import Optional, ClassVar

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID
from ._helpers import ts_cols


class ProposalReview(UUIDMixin, Base):
    __tablename__ = "proposal_reviews"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] = (
        "owner=board_of_education_governing_board; "
        "description=Stores cic proposal reviews records for the application. "
        "References related entities via: proposal, reviewer. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "8 column(s) defined. "
        "Primary key is `id`. "
        "2 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment": (
            "Stores proposal reviews records for the application. "
            "References related entities via: proposal, reviewer. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "8 column(s) defined. "
            "Primary key is `id`. "
            "2 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description": (
                "Stores proposal reviews records for the application. "
                "References related entities via: proposal, reviewer. "
                "Includes standard audit timestamps (created_at, updated_at). "
                "8 column(s) defined. "
                "Primary key is `id`. "
                "2 foreign key field(s) detected."
            ),
        },
    }

    # --- FKs ---
    proposal_id: Mapped[GUID] = mapped_column(
        GUID(),
        sa.ForeignKey("proposals.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    review_round_id: Mapped[GUID] = mapped_column(
        GUID(),
        sa.ForeignKey("review_rounds.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    reviewer_id: Mapped[Optional[GUID]] = mapped_column(
        GUID(),
        sa.ForeignKey("persons.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # --- Fields ---
    decision: Mapped[Optional[str]] = mapped_column(sa.Text)  # approve|reject|revise
    decided_at: Mapped[Optional[datetime]] = mapped_column(sa.DateTime(timezone=True))
    comment: Mapped[Optional[str]] = mapped_column(sa.Text)

    # --- Relationships ---
    proposal: Mapped["Proposal"] = relationship(
        "Proposal",
        back_populates="reviews",          # <-- FIXED (was "proposal_reviews")
        foreign_keys=[proposal_id],
    )

    review_round: Mapped["ReviewRound"] = relationship(
        "ReviewRound",
        back_populates="proposal_reviews",  # must match ReviewRound.proposal_reviews
        foreign_keys=[review_round_id],
    )

    # audit timestamps
    created_at, updated_at = ts_cols()
