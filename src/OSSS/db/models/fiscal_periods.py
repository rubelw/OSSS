from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB, TimestampMixin

class FiscalPeriod(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "fiscal_periods"
    __table_args__ = (sa.UniqueConstraint("fiscal_year_id", "period_no", name="uq_year_periodno"),)

    fiscal_year_id: Mapped[str] = mapped_column(GUID(), sa.ForeignKey("fiscal_years.id", ondelete="CASCADE"), nullable=False)
    period_no: Mapped[int] = mapped_column(sa.Integer, nullable=False)  # 1..12 or 1..13
    start_date: Mapped[date] = mapped_column(sa.Date, nullable=False)
    end_date: Mapped[date] = mapped_column(sa.Date, nullable=False)
    is_closed: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=sa.text("false"))

    year: Mapped["FiscalYear"] = relationship("FiscalYear", back_populates="periods")
    entries: Mapped[list["JournalEntry"]] = relationship("JournalEntry", back_populates="period")
