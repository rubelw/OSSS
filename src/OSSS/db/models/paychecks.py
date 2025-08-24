from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB, TimestampMixin

class Paycheck(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "paychecks"

    run_id: Mapped[str] = mapped_column(GUID(), sa.ForeignKey("payroll_runs.id", ondelete="CASCADE"), nullable=False)
    employee_id: Mapped[str] = mapped_column(GUID(), sa.ForeignKey("hr_employees.id", ondelete="CASCADE"), nullable=False)
    check_no: Mapped[Optional[str]] = mapped_column(sa.String(32))  # or advice number
    gross_pay: Mapped[float] = mapped_column(sa.Numeric(12, 2), nullable=False)
    net_pay: Mapped[float] = mapped_column(sa.Numeric(12, 2), nullable=False)
    taxes: Mapped[Optional[dict]] = mapped_column(JSONB())
    attributes: Mapped[Optional[dict]] = mapped_column(JSONB())

    run: Mapped["PayrollRun"] = relationship("PayrollRun", back_populates="checks")
