from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB, TimestampMixin

class PayPeriod(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "pay_periods"

    code: Mapped[str] = mapped_column(sa.String(32), nullable=False, unique=True)
    start_date: Mapped[date] = mapped_column(sa.Date, nullable=False)
    end_date: Mapped[date] = mapped_column(sa.Date, nullable=False)
    pay_date: Mapped[date] = mapped_column(sa.Date, nullable=False)
    status: Mapped[str] = mapped_column(sa.String(16), nullable=False, server_default=sa.text("'open'"))  # open, locked, posted

    runs: Mapped[list["PayrollRun"]] = relationship("PayrollRun", back_populates="pay_period", cascade="all, delete-orphan")
