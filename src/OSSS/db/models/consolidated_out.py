from __future__ import annotations

from typing import Dict, List
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column
from OSSS.db.base import Base, UUIDMixin, JSONB

__all__ = ["ConsolidatedOut"]


class ConsolidatedOut(UUIDMixin, Base):
    __tablename__ = "consolidated_out"
    __allow_unmapped__ = True

    NOTE: str = (
        "owner=curriculum_instruction_assessment | division_of_schools | ai_tutor_system; "
        "description=Aggregated, student-facing result after consolidating multiple tutor outputs. "
        "References related entities via: sessions, tutor_turns. "
        "Includes standard audit timestamps (created_at). "
        "6 column(s) defined. "
        "Primary key is `id`. "
        "No foreign key fields detected (links stored via references)."
    )

    __table_args__ = {
        "comment": (
            "Aggregated, student-facing result after consolidating multiple tutor outputs. "
            "References related entities via: sessions, tutor_turns. "
            "Includes standard audit timestamps (created_at). "
            "6 column(s) defined. "
            "Primary key is `id`. "
            "No foreign key fields detected (links stored via references)."
        ),
        "info": {
            "note": NOTE,
            "description": (
                "Aggregated, student-facing result after consolidating multiple tutor outputs. "
                "References related entities via: sessions, tutor_turns. "
                "Includes standard audit timestamps (created_at). "
                "6 column(s) defined. "
                "Primary key is `id`. "
                "No foreign key fields detected (links stored via references)."
            ),
        },
    }

    # --- Columns ---
    consolidated_answer: Mapped[str] = mapped_column(sa.Text, nullable=False)
    confidence: Mapped[float] = mapped_column(sa.Float, nullable=False)
    scores: Mapped[Dict[str, float]] = mapped_column(JSONB, nullable=False)
    selected_tutors: Mapped[List[str]] = mapped_column(JSONB, nullable=False)
    rationale: Mapped[str] = mapped_column(sa.Text, nullable=False)

    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )
