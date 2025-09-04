from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List, ClassVar

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB, TimestampMixin

class EmployeeDeduction(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "employee_deductions"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=division_of_finance; "
        "description=Stores employee deductions records for the application. "
        "References related entities via: deduction code, employee, run. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "8 column(s) defined. "
        "Primary key is `id`. "
        "3 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment":         (
            "Stores employee deductions records for the application. "
            "References related entities via: deduction code, employee, run. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "8 column(s) defined. "
            "Primary key is `id`. "
            "3 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores employee deductions records for the application. "
            "References related entities via: deduction code, employee, run. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "8 column(s) defined. "
            "Primary key is `id`. "
            "3 foreign key field(s) detected."
        ),
        },
    }


    run_id: Mapped[str] = mapped_column(GUID(), sa.ForeignKey("payroll_runs.id", ondelete="CASCADE"), nullable=False)
    employee_id: Mapped[str] = mapped_column(GUID(), sa.ForeignKey("hr_employees.id", ondelete="CASCADE"), nullable=False)
    deduction_code_id: Mapped[str] = mapped_column(GUID(), sa.ForeignKey("deduction_codes.id", ondelete="RESTRICT"), nullable=False)

    amount: Mapped[float] = mapped_column(sa.Numeric(12, 2), nullable=False)
    attributes: Mapped[Optional[dict]] = mapped_column(JSONB())

    run: Mapped["PayrollRun"] = relationship("PayrollRun", back_populates="deductions")


