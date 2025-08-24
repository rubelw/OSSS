from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB, TimestampMixin

class EvaluationResponse(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "evaluation_responses"

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
