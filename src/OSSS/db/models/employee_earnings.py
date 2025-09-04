from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List, ClassVar

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB, TimestampMixin

class EmployeeEarning(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "employee_earnings"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=division_of_finance; "
        "description=Stores employee earnings records for the application. "
        "References related entities via: earning code, employee, run. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "9 column(s) defined. "
        "Primary key is `id`. "
        "3 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment":         (
            "Stores employee earnings records for the application. "
            "References related entities via: earning code, employee, run. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "9 column(s) defined. "
            "Primary key is `id`. "
            "3 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores employee earnings records for the application. "
            "References related entities via: earning code, employee, run. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "9 column(s) defined. "
            "Primary key is `id`. "
            "3 foreign key field(s) detected."
        ),
        },
    }


    run_id: Mapped[str] = mapped_column(GUID(), sa.ForeignKey("payroll_runs.id", ondelete="CASCADE"), nullable=False)
    employee_id: Mapped[str] = mapped_column(GUID(), sa.ForeignKey("hr_employees.id", ondelete="CASCADE"), nullable=False)
    earning_code_id: Mapped[str] = mapped_column(GUID(), sa.ForeignKey("earning_codes.id", ondelete="RESTRICT"), nullable=False)

    hours: Mapped[Optional[float]] = mapped_column(sa.Numeric(10, 2))
    rate: Mapped[Optional[float]] = mapped_column(sa.Numeric(12, 4))
    amount: Mapped[float] = mapped_column(sa.Numeric(12, 2), nullable=False)  # hours*rate or flat amount

    run: Mapped["PayrollRun"] = relationship("PayrollRun", back_populates="earnings")


