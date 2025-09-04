
from __future__ import annotations

from typing import Optional, Dict, Any, ClassVar
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, TimestampMixin, GUID, JSON


class Review(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "reviews"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=division_of_technology_data; "
        "description=Stores reviews records for the application. "
        "References related entities via: review round, reviewer. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "8 column(s) defined. "
        "Primary key is `id`. "
        "2 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment":         (
            "Stores reviews records for the application. "
            "References related entities via: review round, reviewer. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "8 column(s) defined. "
            "Primary key is `id`. "
            "2 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores reviews records for the application. "
            "References related entities via: review round, reviewer. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "8 column(s) defined. "
            "Primary key is `id`. "
            "2 foreign key field(s) detected."
        ),
        },
    }

    review_round_id: Mapped[GUID] = mapped_column(
        GUID(),
        sa.ForeignKey("review_rounds.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    reviewer_id: Mapped[str] = mapped_column(GUID(), sa.ForeignKey("reviewers.id", ondelete="CASCADE"), nullable=False, index=True)

    status: Mapped[str] = mapped_column(sa.Enum("draft", "submitted", name="review_status", native_enum=False), nullable=False, server_default="draft")
    submitted_at: Mapped[Optional[sa.DateTime]] = mapped_column(sa.DateTime(timezone=True))
    content: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)

    review_round: Mapped["ReviewRound"] = relationship(
        "ReviewRound",
        back_populates="reviews",
    )

    reviewer = relationship("Reviewer", back_populates="reviews")