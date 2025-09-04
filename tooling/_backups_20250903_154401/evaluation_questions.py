from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB, TimestampMixin

class EvaluationQuestion(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "evaluation_questions"

    section_id: Mapped[str] = mapped_column(
        GUID(), sa.ForeignKey("evaluation_sections.id", ondelete="CASCADE"), nullable=False
    )
    text: Mapped[str] = mapped_column(sa.Text, nullable=False)
    type: Mapped[str] = mapped_column(sa.String(16), nullable=False)  # scale|text|multi
    scale_min: Mapped[Optional[int]] = mapped_column(sa.Integer)
    scale_max: Mapped[Optional[int]] = mapped_column(sa.Integer)
    weight: Mapped[Optional[float]] = mapped_column(sa.Float)

    section: Mapped["EvaluationSection"] = relationship("EvaluationSection", back_populates="questions")
