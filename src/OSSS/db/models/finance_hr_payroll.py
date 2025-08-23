# src/OSSS/db/models/finance_hr_payroll.py
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, GUID, UUIDMixin, TimestampMixin, JSONB


# ==========================
# Finance / General Ledger
# ==========================

class GLSegment(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "gl_segments"

    code: Mapped[str] = mapped_column(sa.String(32), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    seq: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    length: Mapped[Optional[int]] = mapped_column(sa.Integer)
    required: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=sa.text("true"))

    values: Mapped[list["GLSegmentValue"]] = relationship(
        "GLSegmentValue", back_populates="segment", cascade="all, delete-orphan"
    )


class GLSegmentValue(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "gl_segment_values"
    __table_args__ = (sa.UniqueConstraint("segment_id", "code", name="uq_segment_value_code_per_segment"),)

    segment_id: Mapped[str] = mapped_column(GUID(), sa.ForeignKey("gl_segments.id", ondelete="CASCADE"), nullable=False)
    code: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    name: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    active: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=sa.text("true"))

    segment: Mapped["GLSegment"] = relationship("GLSegment", back_populates="values")


class GLAccount(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "gl_accounts"

    code: Mapped[str] = mapped_column(sa.String(128), nullable=False, unique=True)  # full combined code
    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    acct_type: Mapped[str] = mapped_column(sa.String(32), nullable=False)  # asset, liability, revenue, expense, equity
    active: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=sa.text("true"))
    attributes: Mapped[Optional[dict]] = mapped_column(JSONB())

    lines: Mapped[list["JournalEntryLine"]] = relationship("JournalEntryLine", back_populates="account")


class GLAccountSegment(UUIDMixin, TimestampMixin, Base):
    """Optional: store segment/value breakdown for a GL account."""
    __tablename__ = "gl_account_segments"
    __table_args__ = (sa.UniqueConstraint("account_id", "segment_id", name="uq_account_segment_once"),)

    account_id: Mapped[str] = mapped_column(GUID(), sa.ForeignKey("gl_accounts.id", ondelete="CASCADE"), nullable=False)
    segment_id: Mapped[str] = mapped_column(GUID(), sa.ForeignKey("gl_segments.id", ondelete="CASCADE"), nullable=False)
    value_id: Mapped[Optional[str]] = mapped_column(GUID(), sa.ForeignKey("gl_segment_values.id", ondelete="SET NULL"))

# Fiscal

class FiscalYear(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "fiscal_years"

    year: Mapped[int] = mapped_column(sa.Integer, nullable=False, unique=True)  # e.g., 2024
    start_date: Mapped[date] = mapped_column(sa.Date, nullable=False)
    end_date: Mapped[date] = mapped_column(sa.Date, nullable=False)
    is_closed: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=sa.text("false"))

    periods: Mapped[list["FiscalPeriod"]] = relationship(
        "FiscalPeriod", back_populates="year", cascade="all, delete-orphan"
    )


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


class JournalBatch(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "journal_batches"

    batch_no: Mapped[str] = mapped_column(sa.String(64), nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(sa.String(255))
    source: Mapped[Optional[str]] = mapped_column(sa.String(64))         # subsystem/source tag
    status: Mapped[str] = mapped_column(sa.String(16), nullable=False, server_default=sa.text("'open'"))  # open, posted
    posted_at: Mapped[Optional[datetime]] = mapped_column(sa.TIMESTAMP(timezone=True))


class JournalEntry(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "journal_entries"
    __table_args__ = (sa.UniqueConstraint("batch_id", "je_no", name="uq_batch_je_no"),)

    batch_id: Mapped[str] = mapped_column(GUID(), sa.ForeignKey("journal_batches.id", ondelete="CASCADE"), nullable=False)
    fiscal_period_id: Mapped[str] = mapped_column(GUID(), sa.ForeignKey("fiscal_periods.id", ondelete="RESTRICT"), nullable=False)

    je_no: Mapped[str] = mapped_column(sa.String(64), nullable=False)  # unique per batch
    journal_date: Mapped[date] = mapped_column(sa.Date, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(sa.String(255))
    status: Mapped[str] = mapped_column(sa.String(16), nullable=False, server_default=sa.text("'open'"))
    total_debits: Mapped[float] = mapped_column(sa.Numeric(14, 2), nullable=False, server_default="0")
    total_credits: Mapped[float] = mapped_column(sa.Numeric(14, 2), nullable=False, server_default="0")

    batch: Mapped["JournalBatch"] = relationship("JournalBatch", backref="entries")
    period: Mapped["FiscalPeriod"] = relationship("FiscalPeriod", back_populates="entries")
    lines: Mapped[list["JournalEntryLine"]] = relationship(
        "JournalEntryLine", back_populates="entry", cascade="all, delete-orphan"
    )


class JournalEntryLine(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "journal_entry_lines"

    entry_id: Mapped[str] = mapped_column(GUID(), sa.ForeignKey("journal_entries.id", ondelete="CASCADE"), nullable=False)
    account_id: Mapped[str] = mapped_column(GUID(), sa.ForeignKey("gl_accounts.id", ondelete="RESTRICT"), nullable=False)

    line_no: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(sa.String(255))
    debit: Mapped[float] = mapped_column(sa.Numeric(14, 2), nullable=False, server_default="0")
    credit: Mapped[float] = mapped_column(sa.Numeric(14, 2), nullable=False, server_default="0")
    segment_overrides: Mapped[Optional[dict]] = mapped_column(JSONB())

    entry: Mapped["JournalEntry"] = relationship("JournalEntry", back_populates="lines")
    account: Mapped["GLAccount"] = relationship("GLAccount", back_populates="lines")


# ==========================
# HR
# ==========================

class HREmployee(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "hr_employees"

    person_id: Mapped[Optional[str]] = mapped_column(GUID(), sa.ForeignKey("persons.id", ondelete="SET NULL"))
    employee_no: Mapped[str] = mapped_column(sa.String(32), nullable=False, unique=True)
    primary_school_id: Mapped[Optional[str]] = mapped_column(GUID(), sa.ForeignKey("schools.id", ondelete="SET NULL"))

    # matches earlier migration column name (segment, not value):
    department_segment_id: Mapped[Optional[str]] = mapped_column(GUID(), sa.ForeignKey("gl_segments.id", ondelete="SET NULL"))

    employment_type: Mapped[Optional[str]] = mapped_column(sa.String(16))  # full_time, part_time, etc.
    status: Mapped[str] = mapped_column(sa.String(16), nullable=False, server_default=sa.text("'active'"))
    hire_date: Mapped[Optional[date]] = mapped_column(sa.Date)
    termination_date: Mapped[Optional[date]] = mapped_column(sa.Date)
    attributes: Mapped[Optional[dict]] = mapped_column(JSONB())

    assignments: Mapped[list["HRPositionAssignment"]] = relationship(
        "HRPositionAssignment", back_populates="employee", cascade="all, delete-orphan"
    )


class HRPosition(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "hr_positions"

    title: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    department_segment_id: Mapped[Optional[str]] = mapped_column(GUID(), sa.ForeignKey("gl_segments.id", ondelete="SET NULL"))
    grade: Mapped[Optional[str]] = mapped_column(sa.String(32))
    fte: Mapped[Optional[float]] = mapped_column(sa.Numeric(5, 2))
    attributes: Mapped[Optional[dict]] = mapped_column(JSONB())

    assignments: Mapped[list["HRPositionAssignment"]] = relationship(
        "HRPositionAssignment", back_populates="position", cascade="all, delete-orphan"
    )


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


# ==========================
# Payroll
# ==========================

class PayPeriod(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "pay_periods"

    code: Mapped[str] = mapped_column(sa.String(32), nullable=False, unique=True)
    start_date: Mapped[date] = mapped_column(sa.Date, nullable=False)
    end_date: Mapped[date] = mapped_column(sa.Date, nullable=False)
    pay_date: Mapped[date] = mapped_column(sa.Date, nullable=False)
    status: Mapped[str] = mapped_column(sa.String(16), nullable=False, server_default=sa.text("'open'"))  # open, locked, posted

    runs: Mapped[list["PayrollRun"]] = relationship("PayrollRun", back_populates="pay_period", cascade="all, delete-orphan")


class PayrollRun(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "payroll_runs"

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


class EarningCode(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "earning_codes"

    code: Mapped[str] = mapped_column(sa.String(32), nullable=False, unique=True)  # REG, OT, etc.
    name: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    taxable: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=sa.text("true"))
    attributes: Mapped[Optional[dict]] = mapped_column(JSONB())


class DeductionCode(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "deduction_codes"

    code: Mapped[str] = mapped_column(sa.String(32), nullable=False, unique=True)  # 403B, MED, etc.
    name: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    pretax: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=sa.text("true"))
    vendor_id: Mapped[Optional[str]] = mapped_column(GUID(), sa.ForeignKey("vendors.id", ondelete="SET NULL"))
    attributes: Mapped[Optional[dict]] = mapped_column(JSONB())


class EmployeeEarning(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "employee_earnings"

    run_id: Mapped[str] = mapped_column(GUID(), sa.ForeignKey("payroll_runs.id", ondelete="CASCADE"), nullable=False)
    employee_id: Mapped[str] = mapped_column(GUID(), sa.ForeignKey("hr_employees.id", ondelete="CASCADE"), nullable=False)
    earning_code_id: Mapped[str] = mapped_column(GUID(), sa.ForeignKey("earning_codes.id", ondelete="RESTRICT"), nullable=False)

    hours: Mapped[Optional[float]] = mapped_column(sa.Numeric(10, 2))
    rate: Mapped[Optional[float]] = mapped_column(sa.Numeric(12, 4))
    amount: Mapped[float] = mapped_column(sa.Numeric(12, 2), nullable=False)  # hours*rate or flat amount

    run: Mapped["PayrollRun"] = relationship("PayrollRun", back_populates="earnings")


class EmployeeDeduction(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "employee_deductions"

    run_id: Mapped[str] = mapped_column(GUID(), sa.ForeignKey("payroll_runs.id", ondelete="CASCADE"), nullable=False)
    employee_id: Mapped[str] = mapped_column(GUID(), sa.ForeignKey("hr_employees.id", ondelete="CASCADE"), nullable=False)
    deduction_code_id: Mapped[str] = mapped_column(GUID(), sa.ForeignKey("deduction_codes.id", ondelete="RESTRICT"), nullable=False)

    amount: Mapped[float] = mapped_column(sa.Numeric(12, 2), nullable=False)
    attributes: Mapped[Optional[dict]] = mapped_column(JSONB())

    run: Mapped["PayrollRun"] = relationship("PayrollRun", back_populates="deductions")


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
