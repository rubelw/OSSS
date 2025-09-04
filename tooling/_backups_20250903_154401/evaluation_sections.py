from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB, TimestampMixin

class EvaluationSection(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "evaluation_sections"

    template_id: Mapped[str] = mapped_column(
        GUID(), sa.ForeignKey("evaluation_templates.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    order_no: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default="0")

    template: Mapped["EvaluationTemplate"] = relationship("EvaluationTemplate", back_populates="sections")
    questions: Mapped[list["EvaluationQuestion"]] = relationship(
        "EvaluationQuestion", back_populates="section", cascade="all, delete-orphan"
    )
