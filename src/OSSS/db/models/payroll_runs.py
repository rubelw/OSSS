from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List, ClassVar

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB, TimestampMixin

class PayrollRun(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "payroll_runs"
    __allow_unmapped__ = True  # keep NOTE out of the SQLAlchemy mapper

    NOTE: ClassVar[str] =     (
        "owner=business_accounting; "
        "description=Stores payroll runs records for the application. "
        "References related entities via: created by user, pay period, posted entry. "
        "Includes standard audit timestamps (created_at, updated_at). "
        "8 column(s) defined. "
        "Primary key is `id`. "
        "3 foreign key field(s) detected."
    )

    __table_args__ = {
        "comment":         (
            "Stores payroll runs records for the application. "
            "References related entities via: created by user, pay period, posted entry. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "8 column(s) defined. "
            "Primary key is `id`. "
            "3 foreign key field(s) detected."
        ),
        "info": {
            "note": NOTE,
            "description":         (
            "Stores payroll runs records for the application. "
            "References related entities via: created by user, pay period, posted entry. "
            "Includes standard audit timestamps (created_at, updated_at). "
            "8 column(s) defined. "
            "Primary key is `id`. "
            "3 foreign key field(s) detected."
        ),
        },
    }


    pay_period_id: Mapped[str] = mapped_column(GUID(), sa.ForeignKey("pay_periods.id", ondelete="CASCADE"), nullable=False)
    run_no: Mapped[int] = mapped_column(sa.Integer, nullable=False, server_default="1")  # multiple runs per period
    status: Mapped[str] = mapped_column(sa.String(16), nullable=False, server_default=sa.text("'open'"))  # open, processed, posted
    created_by_user_id: Mapped[Optional[str]] = mapped_column(GUID(), sa.ForeignKey("users.id", ondelete="SET NULL"))

    # optional link to GL posting (when payroll posts to GL)
    posted_entry_id: Mapped[Optional[str]] = mapped_column(GUID(), sa.ForeignKey("journal_entries.id", ondelete="SET NULL"))

    pay_period: Mapped["PayPeriod"] = relationship("PayPeriod", back_populates="runs")
    earnings: Mapped[list["EmployeeEarning"]] = relationship("EmployeeEarning", back_populates="run", cascade="all, delete-orphan")
    deductions: Mapped[list["EmployeeDeduction"]] = relationship("EmployeeDeduction", back_populates="run", cascade="all, delete-orphan")
    checks: Mapped[list["Paycheck"]] = relationship("Paycheck", back_populates="run", cascade="all, delete-orphan")


