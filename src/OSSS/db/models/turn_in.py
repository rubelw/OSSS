from __future__ import annotations

from typing import Any, List, Optional
import sqlalchemy as sa
from sqlalchemy import ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column
from OSSS.db.base import Base, UUIDMixin, JSONB, GUID


__all__ = ["TurnIn"]


class TurnIn(UUIDMixin, Base):
    __tablename__ = "turn_in"
    __allow_unmapped__ = True

    NOTE: str = (
        "owner=curriculum_instruction_assessment | division_of_schools | ai_tutor_system; "
        "description=Input payload for an orchestration turn involving multiple tutors. "
        "References related entities via: sessions, tutor_spec. "
        "Includes standard audit timestamps (created_at). "
        "5 column(s) defined. "
        "Primary key is `id`. "
        "1 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment": (
            "Input payload for an orchestration turn involving multiple tutors. "
            "References related entities via: sessions, tutor_spec. "
            "Includes standard audit timestamps (created_at). "
            "5 column(s) defined. "
            "Primary key is `id`. "
            "1 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description": (
                "Input payload for an orchestration turn involving multiple tutors. "
                "References related entities via: sessions, tutor_spec. "
                "Includes standard audit timestamps (created_at). "
                "5 column(s) defined. "
                "Primary key is `id`. "
                "1 foreign key field(s) detected."
            ),
        },
    }

    # --- Columns ---
    # match sessions.id (UUID via UUIDMixin) -> use GUID()
    session_id: Mapped[Any] = mapped_column(
        GUID(), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )

    prompt: Mapped[str] = mapped_column(sa.Text, nullable=False)
    objective_code: Mapped[str] = mapped_column(sa.Text, nullable=False)

    tutors: Mapped[List] = mapped_column(JSONB, nullable=False)

    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )
