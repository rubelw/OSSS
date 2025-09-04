from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List, ClassVar

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB, TimestampMixin

class EvaluationResponse(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "evaluation_responses"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=division_of_technology_data; "
        "description=Stores evaluation responses records for the application. "
        "References related entities via: assignment, question. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "9 column(s) defined. "
        "Primary key is `id`. "
        "2 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment":         (
            "Stores evaluation responses records for the application. "
            "References related entities via: assignment, question. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "9 column(s) defined. "
            "Primary key is `id`. "
            "2 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores evaluation responses records for the application. "
            "References related entities via: assignment, question. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "9 column(s) defined. "
            "Primary key is `id`. "
            "2 foreign key field(s) detected."
        ),
        },
    }


    assignment_id: Mapped[str] = mapped_column(
        GUID(), sa.ForeignKey("evaluation_assignments.id", ondelete="CASCADE"), nullable=False
    )
    question_id: Mapped[str] = mapped_column(
        GUID(), sa.ForeignKey("evaluation_questions.id", ondelete="CASCADE"), nullable=False
    )
    value_num: Mapped[Optional[float]] = mapped_column(sa.Float)
    value_text: Mapped[Optional[str]] = mapped_column(sa.Text)
    comment: Mapped[Optional[str]] = mapped_column(sa.Text)
    answered_at: Mapped[Optional[datetime]] = mapped_column(sa.TIMESTAMP(timezone=True))

    assignment: Mapped["EvaluationAssignment"] = relationship("EvaluationAssignment", back_populates="responses")
    question: Mapped["EvaluationQuestion"] = relationship("EvaluationQuestion")


