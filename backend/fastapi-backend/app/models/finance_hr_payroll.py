from __future__ import annotations
from datetime import datetime, date
from typing import Optional
from sqlalchemy import Column, Text, CHAR, Date, DateTime, Numeric, TIMESTAMP, func, Integer, Boolean, ForeignKey, UniqueConstraint, String, CheckConstraint
from sqlalchemy.sql import text
from sqlalchemy.orm import relationship
import sqlalchemy as sa

from .base import Base, GUID, UUIDMixin, JSONB

# ---------- helpers ----------
def ts_cols():
    return (
        Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now()),
        Column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()),
    )



# ==========================
# Finance / General Ledger
# ==========================

class GLSegment(UUIDMixin, Base):
    __tablename__ = "gl_segments"

    code = Column(String(32), nullable=False, unique=True)
    name = Column(String(128), nullable=False)
    seq = Column(Integer, nullable=False)            # ordering of segments in an account string
    length = Column(Integer, nullable=True)          # optional fixed length
    required = Column(Boolean, nullable=False, server_default="true")

    created_at, updated_at = ts_cols()

    values = relationship("GLSegmentValue", back_populates="segment", cascade="all, delete-orphan")


class GLSegmentValue(UUIDMixin, Base):
    __tablename__ = "gl_segment_values"
    __table_args__ = (UniqueConstraint("segment_id", "code", name="uq_segment_value_code_per_segment"),)

    segment_id = Column(GUID(), ForeignKey("gl_segments.id", ondelete="CASCADE"), nullable=False)
    code = Column(String(32), nullable=False)
    name = Column(String(128), nullable=False)
    active = Column(Boolean, nullable=False, server_default="true")

    created_at, updated_at = ts_cols()

    segment = relationship("GLSegment", back_populates="values")


class GLAccount(UUIDMixin, Base):
    __tablename__ = "gl_accounts"

    code = Column(String(128), nullable=False, unique=True)  # full combined code, e.g., 10-2340-000-...
    name = Column(String(255), nullable=False)
    acct_type = Column(String(32), nullable=False)           # asset, liability, revenue, expense, equity
    active = Column(Boolean, nullable=False, server_default="true")
    attributes = Column(JSONB, nullable=True)

    created_at, updated_at = ts_cols()

    lines = relationship("JournalEntryLine", back_populates="account")


class GLAccountSegment(UUIDMixin, Base):
    """
    Optional: stores the segment/value breakdown for a GL account.
    """
    __tablename__ = "gl_account_segments"
    __table_args__ = (UniqueConstraint("account_id", "segment_id", name="uq_account_segment_once"),)

    account_id = Column(GUID(), ForeignKey("gl_accounts.id", ondelete="CASCADE"), nullable=False)
    segment_id = Column(GUID(), ForeignKey("gl_segments.id", ondelete="CASCADE"), nullable=False)
    value_id = Column(GUID(), ForeignKey("gl_segment_values.id", ondelete="SET NULL"), nullable=True)

    created_at, updated_at = ts_cols()


class FiscalYear(UUIDMixin, Base):
    __tablename__ = "fiscal_years"

    year = Column(Integer, nullable=False, unique=True)  # e.g., 2024
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    is_closed = Column(Boolean, nullable=False, server_default="false")

    created_at, updated_at = ts_cols()

    periods = relationship("FiscalPeriod", back_populates="year", cascade="all, delete-orphan")


class FiscalPeriod(UUIDMixin, Base):
    __tablename__ = "fiscal_periods"
    __table_args__ = (UniqueConstraint("fiscal_year_id", "period_no", name="uq_year_periodno"),)

    fiscal_year_id = Column(GUID(), ForeignKey("fiscal_years.id", ondelete="CASCADE"), nullable=False)
    period_no = Column(Integer, nullable=False)   # 1..12 or 1..13
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    is_closed = Column(Boolean, nullable=False, server_default="false")

    created_at, updated_at = ts_cols()

    year = relationship("FiscalYear", back_populates="periods")
    entries = relationship("JournalEntry", back_populates="period")


class JournalBatch(UUIDMixin, Base):
    __tablename__ = "journal_batches"

    batch_no = Column(String(64), nullable=False, unique=True)
    description = Column(String(255), nullable=True)
    source = Column(String(64), nullable=True)     # subsystem/source tag
    status = Column(String(16), nullable=False, server_default="open")  # open, posted
    posted_at = Column(TIMESTAMP(timezone=True), nullable=True)

    created_at, updated_at = ts_cols()

    entries = relationship("JournalEntry", back_populates="batch")


class JournalEntry(UUIDMixin, Base):
    __tablename__ = "journal_entries"
    __table_args__ = (UniqueConstraint("batch_id", "je_no", name="uq_batch_je_no"),)

    batch_id = Column(GUID(), ForeignKey("journal_batches.id", ondelete="CASCADE"), nullable=False)
    fiscal_period_id = Column(GUID(), ForeignKey("fiscal_periods.id", ondelete="RESTRICT"), nullable=False)

    je_no = Column(String(64), nullable=False)  # unique per batch
    journal_date = Column(Date, nullable=False)
    description = Column(String(255), nullable=True)
    status = Column(String(16), nullable=False, server_default="open")  # open, posted
    total_debits = Column(Numeric(14, 2), nullable=False, default=0)
    total_credits = Column(Numeric(14, 2), nullable=False, default=0)

    created_at, updated_at = ts_cols()

    batch = relationship("JournalBatch", back_populates="entries")
    period = relationship("FiscalPeriod", back_populates="entries")
    lines = relationship("JournalEntryLine", back_populates="entry", cascade="all, delete-orphan")


class JournalEntryLine(UUIDMixin, Base):
    __tablename__ = "journal_entry_lines"

    entry_id = Column(GUID(), ForeignKey("journal_entries.id", ondelete="CASCADE"), nullable=False)
    account_id = Column(GUID(), ForeignKey("gl_accounts.id", ondelete="RESTRICT"), nullable=False)
    line_no = Column(Integer, nullable=False)
    description = Column(String(255), nullable=True)
    debit = Column(Numeric(14, 2), nullable=False, default=0)
    credit = Column(Numeric(14, 2), nullable=False, default=0)
    segment_overrides = Column(JSONB, nullable=True)  # optional: override account's default segments

    created_at, updated_at = ts_cols()

    entry = relationship("JournalEntry", back_populates="lines")
    account = relationship("GLAccount", back_populates="lines")


# ==========================
# HR
# ==========================

class HREmployee(UUIDMixin, Base):
    __tablename__ = "hr_employees"

    person_id = Column(GUID(), ForeignKey("persons.id", ondelete="SET NULL"), nullable=True)
    employee_no = Column(String(32), nullable=False, unique=True)
    primary_school_id = Column(GUID(), ForeignKey("schools.id", ondelete="SET NULL"), nullable=True)

    # Matches earlier migration column name (segment, not value) for compatibility:
    department_segment_id = Column(GUID(), ForeignKey("gl_segments.id", ondelete="SET NULL"), nullable=True)

    employment_type = Column(String(16), nullable=True)  # full_time, part_time, seasonal, etc.
    status = Column(String(16), nullable=False, server_default="active")
    hire_date = Column(Date, nullable=True)
    termination_date = Column(Date, nullable=True)
    attributes = Column(JSONB, nullable=True)

    created_at, updated_at = ts_cols()

    assignments = relationship("HRPositionAssignment", back_populates="employee", cascade="all, delete-orphan")


class HRPosition(UUIDMixin, Base):
    __tablename__ = "hr_positions"

    title = Column(String(255), nullable=False)
    department_segment_id = Column(GUID(), ForeignKey("gl_segments.id", ondelete="SET NULL"), nullable=True)
    grade = Column(String(32), nullable=True)
    fte = Column(Numeric(5, 2), nullable=True)
    attributes = Column(JSONB, nullable=True)

    created_at, updated_at = ts_cols()

    assignments = relationship("HRPositionAssignment", back_populates="position", cascade="all, delete-orphan")


class HRPositionAssignment(UUIDMixin, Base):
    __tablename__ = "hr_position_assignments"

    employee_id = Column(GUID(), ForeignKey("hr_employees.id", ondelete="CASCADE"), nullable=False)
    position_id = Column(GUID(), ForeignKey("hr_positions.id", ondelete="CASCADE"), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)
    percent = Column(Numeric(5, 2), nullable=True)  # allocation percent
    funding_split = Column(JSONB, nullable=True)     # list of {gl_account_id, percent}

    created_at, updated_at = ts_cols()

    employee = relationship("HREmployee", back_populates="assignments")
    position = relationship("HRPosition", back_populates="assignments")


# ==========================
# Payroll
# ==========================

class PayPeriod(UUIDMixin, Base):
    __tablename__ = "pay_periods"

    code = Column(String(32), nullable=False, unique=True)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    pay_date = Column(Date, nullable=False)
    status = Column(String(16), nullable=False, server_default="open")  # open, locked, posted

    created_at, updated_at = ts_cols()

    runs = relationship("PayrollRun", back_populates="pay_period", cascade="all, delete-orphan")


class PayrollRun(UUIDMixin, Base):
    __tablename__ = "payroll_runs"

    pay_period_id = Column(GUID(), ForeignKey("pay_periods.id", ondelete="CASCADE"), nullable=False)
    run_no = Column(Integer, nullable=False, default=1)  # multiple runs in a period
    status = Column(String(16), nullable=False, server_default="open")  # open, processed, posted
    created_by_user_id = Column(GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # optional link to GL posting (when payroll posts to GL)
    posted_entry_id = Column(GUID(), ForeignKey("journal_entries.id", ondelete="SET NULL"), nullable=True)

    created_at, updated_at = ts_cols()

    pay_period = relationship("PayPeriod", back_populates="runs")
    earnings = relationship("EmployeeEarning", back_populates="run", cascade="all, delete-orphan")
    deductions = relationship("EmployeeDeduction", back_populates="run", cascade="all, delete-orphan")
    checks = relationship("Paycheck", back_populates="run", cascade="all, delete-orphan")


class EarningCode(UUIDMixin, Base):
    __tablename__ = "earning_codes"

    code = Column(String(32), nullable=False, unique=True)  # REG, OT, STIP, etc.
    name = Column(String(128), nullable=False)
    taxable = Column(Boolean, nullable=False, server_default="true")
    attributes = Column(JSONB, nullable=True)

    created_at, updated_at = ts_cols()


class DeductionCode(UUIDMixin, Base):
    __tablename__ = "deduction_codes"

    code = Column(String(32), nullable=False, unique=True)  # 403B, MED, DENTAL, GARN, etc.
    name = Column(String(128), nullable=False)
    pretax = Column(Boolean, nullable=False, server_default="true")
    vendor_id = Column(GUID(), ForeignKey("vendors.id", ondelete="SET NULL"), nullable=True)  # optional linkage
    attributes = Column(JSONB, nullable=True)

    created_at, updated_at = ts_cols()


class EmployeeEarning(UUIDMixin, Base):
    __tablename__ = "employee_earnings"

    run_id = Column(GUID(), ForeignKey("payroll_runs.id", ondelete="CASCADE"), nullable=False)
    employee_id = Column(GUID(), ForeignKey("hr_employees.id", ondelete="CASCADE"), nullable=False)
    earning_code_id = Column(GUID(), ForeignKey("earning_codes.id", ondelete="RESTRICT"), nullable=False)

    hours = Column(Numeric(10, 2), nullable=True)
    rate = Column(Numeric(12, 4), nullable=True)
    amount = Column(Numeric(12, 2), nullable=False)  # use either hours*rate or flat amount

    created_at, updated_at = ts_cols()

    run = relationship("PayrollRun", back_populates="earnings")


class EmployeeDeduction(UUIDMixin, Base):
    __tablename__ = "employee_deductions"

    run_id = Column(GUID(), ForeignKey("payroll_runs.id", ondelete="CASCADE"), nullable=False)
    employee_id = Column(GUID(), ForeignKey("hr_employees.id", ondelete="CASCADE"), nullable=False)
    deduction_code_id = Column(GUID(), ForeignKey("deduction_codes.id", ondelete="RESTRICT"), nullable=False)

    amount = Column(Numeric(12, 2), nullable=False)
    attributes = Column(JSONB, nullable=True)

    created_at, updated_at = ts_cols()

    run = relationship("PayrollRun", back_populates="deductions")


class Paycheck(UUIDMixin, Base):
    __tablename__ = "paychecks"

    run_id = Column(GUID(), ForeignKey("payroll_runs.id", ondelete="CASCADE"), nullable=False)
    employee_id = Column(GUID(), ForeignKey("hr_employees.id", ondelete="CASCADE"), nullable=False)
    check_no = Column(String(32), nullable=True)  # or advice number
    gross_pay = Column(Numeric(12, 2), nullable=False)
    net_pay = Column(Numeric(12, 2), nullable=False)
    taxes = Column(JSONB, nullable=True)  # breakdown
    attributes = Column(JSONB, nullable=True)

    created_at, updated_at = ts_cols()

    run = relationship("PayrollRun", back_populates="checks")