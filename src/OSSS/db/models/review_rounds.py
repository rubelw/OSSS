from __future__ import annotations

from typing import List, Optional, ClassVar
from datetime import datetime
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, TimestampMixin, GUID


class ReviewRound(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "review_rounds"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] = (
        "owner=division_of_technology_data; "
        "description=Stores review rounds records for the application. "
        "References related entities via: proposal. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "8 column(s) defined. "
        "Primary key is `id`. "
        "1 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment": (
            "Stores review rounds records for the application. "
            "References related entities via: proposal. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "8 column(s) defined. "
            "Primary key is `id`. "
            "1 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description": (
                "Stores review rounds records for the application. "
                "References related entities via: proposal. "
                "Includes standard audit timestamps (created_at, updated_at). "
                "8 column(s) defined. "
                "Primary key is `id`. "
                "1 foreign key field(s) detected."
            ),
        },
    }

    round_no: Mapped[int] = mapped_column(sa.Integer, nullable=False)

    opened_at: Mapped[Optional[datetime]] = mapped_column(sa.DateTime(timezone=True))
    closed_at: Mapped[Optional[datetime]] = mapped_column(sa.DateTime(timezone=True))
    status: Mapped[Optional[str]] = mapped_column(
        sa.Enum("open", "closed", "canceled", name="review_round_status", native_enum=False),
        server_default="open",
    )

    # FK to proposals.id
    proposal_id: Mapped[GUID] = mapped_column(
        GUID(),
        sa.ForeignKey("proposals.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    proposal: Mapped["Proposal"] = relationship(
        "Proposal",
        back_populates="review_rounds",
    )

    # Collection of *ProposalReview* rows for this round
    proposal_reviews: Mapped[List["ProposalReview"]] = relationship(
        "ProposalReview",
        back_populates="review_round",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
    )

    # Collection of legacy/other *Review* rows for this round (satisfies Review.review_round.back_populates="reviews")
    reviews: Mapped[List["Review"]] = relationship(
        "Review",
        back_populates="review_round",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
    )

    # One-to-one decision for this round
    decision: Mapped[Optional["RoundDecision"]] = relationship(
        "RoundDecision",
        back_populates="review_round",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
    )
