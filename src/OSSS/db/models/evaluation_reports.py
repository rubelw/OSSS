from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB, TimestampMixin

class EvaluationReport(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "evaluation_reports"

    cycle_id: Mapped[str] = mapped_column(
        GUID(), sa.ForeignKey("evaluation_cycles.id", ondelete="CASCADE"), nullable=False
    )
    scope: Mapped[Optional[dict]] = mapped_column(JSONB())
    generated_at: Mapped[datetime] = mapped_column(sa.TIMESTAMP(timezone=True), nullable=False)
    file_id: Mapped[Optional[str]] = mapped_column(GUID(), sa.ForeignKey("files.id", ondelete="SET NULL"))

    cycle: Mapped["EvaluationCycle"] = relationship("EvaluationCycle", back_populates="reports")
