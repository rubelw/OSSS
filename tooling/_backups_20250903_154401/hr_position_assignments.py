from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB, TimestampMixin

class HRPositionAssignment(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "hr_position_assignments"

    employee_id: Mapped[str] = mapped_column(GUID(), sa.ForeignKey("hr_employees.id", ondelete="CASCADE"), nullable=False)
    position_id: Mapped[str] = mapped_column(GUID(), sa.ForeignKey("hr_positions.id", ondelete="CASCADE"), nullable=False)
    start_date: Mapped[date] = mapped_column(sa.Date, nullable=False)
    end_date: Mapped[Optional[date]] = mapped_column(sa.Date)
    percent: Mapped[Optional[float]] = mapped_column(sa.Numeric(5, 2))  # allocation percent
    funding_split: Mapped[Optional[dict]] = mapped_column(JSONB())       # list of {gl_account_id, percent}

    employee: Mapped["HREmployee"] = relationship("HREmployee", back_populates="assignments")
    position: Mapped["HRPosition"] = relationship("HRPosition", back_populates="assignments")
