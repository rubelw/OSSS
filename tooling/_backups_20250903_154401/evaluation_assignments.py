from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB, TimestampMixin

class EvaluationAssignment(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "evaluation_assignments"

    cycle_id: Mapped[str] = mapped_column(
        GUID(), sa.ForeignKey("evaluation_cycles.id", ondelete="CASCADE"), nullable=False
    )
    subject_user_id: Mapped[str] = mapped_column(GUID(), sa.ForeignKey("users.id"), nullable=False)
    evaluator_user_id: Mapped[str] = mapped_column(GUID(), sa.ForeignKey("users.id"), nullable=False)
    template_id: Mapped[str] = mapped_column(
        GUID(), sa.ForeignKey("evaluation_templates.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[Optional[str]] = mapped_column(sa.String(32))

    cycle: Mapped["EvaluationCycle"] = relationship("EvaluationCycle", back_populates="assignments")
    template: Mapped["EvaluationTemplate"] = relationship("EvaluationTemplate", back_populates="assignments")
    responses: Mapped[list["EvaluationResponse"]] = relationship(
        "EvaluationResponse", back_populates="assignment", cascade="all, delete-orphan"
    )
    signoffs: Mapped[list["EvaluationSignoff"]] = relationship(
        "EvaluationSignoff", back_populates="assignment", cascade="all, delete-orphan"
    )
