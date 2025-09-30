from __future__ import annotations

from typing import List
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from OSSS.db.base import Base, UUIDMixin, JSONB

__all__ = ["TutorSpec"]


class TutorSpec(UUIDMixin, Base):
    __tablename__ = "tutor_spec"
    __allow_unmapped__ = True

    NOTE: str = (
        "owner=curriculum_instruction_assessment | division_of_schools | ai_tutor_system; "
        "description=Specification for invoking a particular tutor/agent. "
        "References related entities via: turn_in. "
        "Includes standard audit timestamps (created_at). "
        "4 column(s) defined. "
        "Primary key is `id`. "
        "No foreign key field(s) detected."
    )

    __table_args__ = {
        "comment": (
            "Specification for invoking a particular tutor/agent. "
            "References related entities via: turn_in. "
            "Includes standard audit timestamps (created_at). "
            "4 column(s) defined. "
            "Primary key is `id`. "
            "No foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description": (
                "Specification for invoking a particular tutor/agent. "
                "References related entities via: turn_in. "
                "Includes standard audit timestamps (created_at). "
                "4 column(s) defined. "
                "Primary key is `id`. "
                "No foreign key field(s) detected."
            ),
        },
    }

    # --- Columns ---
    tutor_id: Mapped[str] = mapped_column("id", sa.Text, nullable=False, index=True)
    weight: Mapped[float] = mapped_column(sa.Float, nullable=False, server_default="1.0")
    domain: Mapped[List[str]] = mapped_column(JSONB, nullable=False, server_default="[]")

    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )
