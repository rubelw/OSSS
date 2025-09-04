
from __future__ import annotations

from typing import Optional, ClassVar
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, TimestampMixin, GUID


class RoundDecision(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "round_decisions"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=division_of_technology_data; "
        "description=Stores round decisions records for the application. "
        "References related entities via: review round. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "7 column(s) defined. "
        "Primary key is `id`. "
        "1 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment":         (
            "Stores round decisions records for the application. "
            "References related entities via: review round. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "7 column(s) defined. "
            "Primary key is `id`. "
            "1 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores round decisions records for the application. "
            "References related entities via: review round. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "7 column(s) defined. "
            "Primary key is `id`. "
            "1 foreign key field(s) detected."
        ),
        },
    }

    # ✅ FK back to review_rounds (unique for 1:1)
    review_round_id: Mapped[GUID] = mapped_column(
        GUID(),
        sa.ForeignKey("review_rounds.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        unique=True,  # enforce one-to-one
    )

    decision: Mapped[str] = mapped_column(sa.Enum(
        "approved", "approved_with_conditions", "revisions_requested", "rejected",
        name="round_decision", native_enum=False
    ), nullable=False)


    decided_at: Mapped[Optional[sa.DateTime]] = mapped_column(sa.DateTime(timezone=True))
    notes: Mapped[Optional[str]] = mapped_column(sa.Text)

    round = relationship("ReviewRound", back_populates="decision")

    review_round: Mapped["ReviewRound"] = relationship(
        "ReviewRound", back_populates="decision"
    )