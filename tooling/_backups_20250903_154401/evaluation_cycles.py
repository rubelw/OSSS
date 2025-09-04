from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB, TimestampMixin

class EvaluationCycle(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "evaluation_cycles"

    org_id: Mapped[str] = mapped_column(GUID(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    start_at: Mapped[Optional[datetime]] = mapped_column(sa.TIMESTAMP(timezone=True))
    end_at: Mapped[Optional[datetime]] = mapped_column(sa.TIMESTAMP(timezone=True))

    assignments: Mapped[list["EvaluationAssignment"]] = relationship(
        "EvaluationAssignment", back_populates="cycle", cascade="all, delete-orphan"
    )
    reports: Mapped[list["EvaluationReport"]] = relationship(
        "EvaluationReport", back_populates="cycle", cascade="all, delete-orphan"
    )
