from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB, TimestampMixin

class EmployeeDeduction(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "employee_deductions"

    run_id: Mapped[str] = mapped_column(GUID(), sa.ForeignKey("payroll_runs.id", ondelete="CASCADE"), nullable=False)
    employee_id: Mapped[str] = mapped_column(GUID(), sa.ForeignKey("hr_employees.id", ondelete="CASCADE"), nullable=False)
    deduction_code_id: Mapped[str] = mapped_column(GUID(), sa.ForeignKey("deduction_codes.id", ondelete="RESTRICT"), nullable=False)

    amount: Mapped[float] = mapped_column(sa.Numeric(12, 2), nullable=False)
    attributes: Mapped[Optional[dict]] = mapped_column(JSONB())

    run: Mapped["PayrollRun"] = relationship("PayrollRun", back_populates="deductions")
