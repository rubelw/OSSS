from __future__ import annotations

from typing import Any, Dict
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from OSSS.db.base import Base, UUIDMixin, JSONB

__all__ = ["TutorOut"]


class TutorOut(UUIDMixin, Base):
    __tablename__ = "tutor_out"
    __allow_unmapped__ = True

    NOTE: str = (
        "owner=curriculum_instruction_assessment | division_of_schools | ai_tutor_system; "
        "description=Normalized output from a single tutor/agent for a given turn. "
        "References related entities via: turn_in. "
        "Includes standard audit timestamps (created_at). "
        "6 column(s) defined. "
        "Primary key is `id`. "
        "1 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment": (
            "Normalized output from a single tutor/agent for a given turn. "
            "References related entities via: turn_in. "
            "Includes standard audit timestamps (created_at). "
            "6 column(s) defined. "
            "Primary key is `id`. "
            "1 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description": (
                "Normalized output from a single tutor/agent for a given turn. "
                "References related entities via: turn_in. "
                "Includes standard audit timestamps (created_at). "
                "6 column(s) defined. "
                "Primary key is `id`. "
                "1 foreign key field(s) detected."
            ),
        },
    }

    # --- Columns ---
    tutor_id: Mapped[str] = mapped_column(sa.Text, nullable=False)
    response: Mapped[str] = mapped_column(sa.Text, nullable=False)
    evidence: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    score: Mapped[float] = mapped_column(sa.Float, nullable=False)
    confidence: Mapped[float] = mapped_column(sa.Float, nullable=False)

    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )

