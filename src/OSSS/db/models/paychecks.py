from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List, ClassVar

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB, TimestampMixin

class Paycheck(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "paychecks"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=business_accounting; "
        "description=Stores paychecks records for the application. "
        "References related entities via: employee, run. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "10 column(s) defined. "
        "Primary key is `id`. "
        "2 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment":         (
            "Stores paychecks records for the application. "
            "References related entities via: employee, run. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "10 column(s) defined. "
            "Primary key is `id`. "
            "2 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores paychecks records for the application. "
            "References related entities via: employee, run. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "10 column(s) defined. "
            "Primary key is `id`. "
            "2 foreign key field(s) detected."
        ),
        },
    }


    run_id: Mapped[str] = mapped_column(GUID(), sa.ForeignKey("payroll_runs.id", ondelete="CASCADE"), nullable=False)
    employee_id: Mapped[str] = mapped_column(GUID(), sa.ForeignKey("hr_employees.id", ondelete="CASCADE"), nullable=False)
    check_no: Mapped[Optional[str]] = mapped_column(sa.String(32))  # or advice number
    gross_pay: Mapped[float] = mapped_column(sa.Numeric(12, 2), nullable=False)
    net_pay: Mapped[float] = mapped_column(sa.Numeric(12, 2), nullable=False)
    taxes: Mapped[Optional[dict]] = mapped_column(JSONB())
    attributes: Mapped[Optional[dict]] = mapped_column(JSONB())

    run: Mapped["PayrollRun"] = relationship("PayrollRun", back_populates="checks")


