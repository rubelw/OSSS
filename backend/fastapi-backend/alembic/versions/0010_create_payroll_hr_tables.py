from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# Pull the shims from your app (preferred)
try:
    from app.models.base import GUID, JSONB, TSVectorType  # GUID/JSONB TypeDecorator; TSVectorType for PG tsvector
except Exception:
    import uuid
    from sqlalchemy.types import TypeDecorator, CHAR

    class GUID(TypeDecorator):
        impl = CHAR
        cache_ok = True
        def load_dialect_impl(self, dialect):
            if dialect.name == "postgresql":
                from sqlalchemy.dialects.postgresql import UUID as PGUUID
                return dialect.type_descriptor(PGUUID(as_uuid=True))
            return dialect.type_descriptor(sa.CHAR(36))
        def process_bind_param(self, value, dialect):
            if value is None:
                return None
            if not isinstance(value, uuid.UUID):
                value = uuid.UUID(str(value))
            return str(value)
        def process_result_value(self, value, dialect):
            return None if value is None else uuid.UUID(value)

    try:
        from sqlalchemy.dialects.postgresql import JSONB as PGJSONB
    except Exception:
        PGJSONB = None

    class JSONB(TypeDecorator):
        impl = sa.JSON
        cache_ok = True
        def load_dialect_impl(self, dialect):
            if dialect.name == "postgresql" and PGJSONB is not None:
                return dialect.type_descriptor(PGJSONB())
            return dialect.type_descriptor(sa.JSON())

    try:
        from sqlalchemy.dialects.postgresql import TSVECTOR as PG_TSVECTOR
        class TSVectorType(PG_TSVECTOR):
            pass
    except Exception:
        class TSVectorType(sa.Text):
            pass

# --- Alembic identifiers ---
revision = "0010_create_payroll_hr_tables"
down_revision = "0009_create_finance_tables"
branch_labels = None
depends_on = None

# ---- Timestamp helpers ----
def _timestamps():
    return (
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )

def upgrade():
    conn = op.get_bind()
    is_pg = conn.dialect.name == "postgresql"

    # Enable gen_random_uuid() on Postgres
    if is_pg:
        conn.execute(sa.text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))

    def id_col():
        return sa.Column(
            "id",
            sa.String(36),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()") if is_pg else None,
        )

    # ===========================
    # HR Core
    # ===========================
    # Employees
    op.create_table(
        "hr_employees",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("person_id", sa.String(36), sa.ForeignKey("persons.id", ondelete="SET NULL"), nullable=True),
        sa.Column("employee_no", sa.String(32), nullable=False, unique=True),
        sa.Column("primary_school_id", sa.String(36), sa.ForeignKey("schools.id", ondelete="SET NULL"),
                  nullable=True),
        # Optional link to a GL “department/segment” row (created in your finance/GL migration)
        sa.Column("department_segment_id", sa.String(36), sa.ForeignKey("gl_segments.id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("employment_type", sa.String(16), nullable=True),  # full_time, part_time, temp, etc.
        sa.Column("status", sa.String(16), nullable=False, server_default=sa.text("'active'")),
        sa.Column("hire_date", sa.Date, nullable=True),
        sa.Column("termination_date", sa.Date, nullable=True),
        sa.Column("attributes", JSONB(), nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_hr_employees_person", "hr_employees", ["person_id"])
    op.create_index("ix_hr_employees_deptseg", "hr_employees", ["department_segment_id"])

    op.create_table(
        "hr_positions",
        id_col(),
        sa.Column("code", sa.String(32), nullable=False, unique=True),     # TEACH-EL, CUST-1, ADMIN-AP
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("flsa_status", sa.String(8), nullable=True),             # exempt/nonexempt
        sa.Column("class_type", sa.String(16), nullable=True),             # certified/classified/admin
        sa.Column("default_account_id", sa.String(36), sa.ForeignKey("gl_accounts.id", ondelete="SET NULL")),
        sa.Column("attributes", JSONB, nullable=True),
        *_timestamps(),
    )

    op.create_table(
        "hr_pay_grades",
        id_col(),
        sa.Column("code", sa.String(32), nullable=False, unique=True),     # G1, TCH-BA, ADMIN-A
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("pay_type", sa.String(16), nullable=False, server_default=sa.text("'salary'")),  # salary/hourly
        sa.Column("attributes", JSONB, nullable=True),
        *_timestamps(),
    )

    op.create_table(
        "hr_pay_steps",
        id_col(),
        sa.Column("grade_id", sa.String(36), sa.ForeignKey("hr_pay_grades.id", ondelete="CASCADE"), nullable=False),
        sa.Column("step_no", sa.Integer, nullable=False),
        sa.Column("annual_rate", sa.Numeric(14, 2), nullable=True),
        sa.Column("hourly_rate", sa.Numeric(14, 4), nullable=True),
        sa.Column("attributes", JSONB, nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("grade_id", "step_no", name="uq_grade_step"),
    )
    op.create_index("ix_hr_pay_steps_grade", "hr_pay_steps", ["grade_id"])

    op.create_table(
        "hr_job_assignments",
        id_col(),
        sa.Column("employee_id", sa.String(36), sa.ForeignKey("hr_employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position_id", sa.String(36), sa.ForeignKey("hr_positions.id", ondelete="SET NULL")),
        sa.Column("school_id", sa.String(36), sa.ForeignKey("schools.id", ondelete="SET NULL")),
        sa.Column("start_date", sa.Date, nullable=False),
        sa.Column("end_date", sa.Date, nullable=True),
        sa.Column("fte", sa.Numeric(5, 4), nullable=True),            # 1.0, 0.5, etc.
        sa.Column("hours_per_day", sa.Numeric(5, 2), nullable=True),
        sa.Column("pay_grade_id", sa.String(36), sa.ForeignKey("hr_pay_grades.id", ondelete="SET NULL")),
        sa.Column("pay_step_id", sa.String(36), sa.ForeignKey("hr_pay_steps.id", ondelete="SET NULL")),
        sa.Column("attributes", JSONB, nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("employee_id", "position_id", "school_id", "start_date",
                            name="uq_job_assign_unique_span"),
    )
    op.create_index("ix_job_assign_emp", "hr_job_assignments", ["employee_id"])
    op.create_index("ix_job_assign_school", "hr_job_assignments", ["school_id"])

    # ===========================
    # Time & Leave
    # ===========================
    op.create_table(
        "time_codes",
        id_col(),
        sa.Column("code", sa.String(16), nullable=False, unique=True),  # REG, OT, DT
        sa.Column("description", sa.String(255), nullable=False),
        sa.Column("earnings_code", sa.String(36), nullable=True),       # link to payroll_earnings_codes after creation (optional)
        sa.Column("is_overtime", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("multiplier", sa.Numeric(6, 3), nullable=True),       # 1.5, 2.0, etc.
        sa.Column("attributes", JSONB, nullable=True),
        *_timestamps(),
    )

    op.create_table(
        "timesheets",
        id_col(),
        sa.Column("employee_id", sa.String(36), sa.ForeignKey("hr_employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("period_start", sa.Date, nullable=False),
        sa.Column("period_end", sa.Date, nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default=sa.text("'open'")),  # open, submitted, approved, exported
        sa.Column("attributes", JSONB, nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("employee_id", "period_start", "period_end", name="uq_timesheet_period"),
    )
    op.create_index("ix_timesheets_emp", "timesheets", ["employee_id"])

    op.create_table(
        "timesheet_lines",
        id_col(),
        sa.Column("timesheet_id", sa.String(36), sa.ForeignKey("timesheets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("work_date", sa.Date, nullable=False),
        sa.Column("job_assignment_id", sa.String(36), sa.ForeignKey("hr_job_assignments.id", ondelete="SET NULL")),
        sa.Column("time_code_id", sa.String(36), sa.ForeignKey("time_codes.id", ondelete="SET NULL")),
        sa.Column("hours", sa.Numeric(6, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("attributes", JSONB, nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_timesheet_lines_sheet", "timesheet_lines", ["timesheet_id"])

    op.create_table(
        "leave_types",
        id_col(),
        sa.Column("code", sa.String(16), nullable=False, unique=True),  # SICK, VAC, PERS, FMLA
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("is_paid", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("attributes", JSONB, nullable=True),  # accrual rules, caps
        *_timestamps(),
    )

    op.create_table(
        "leave_balances",
        id_col(),
        sa.Column("employee_id", sa.String(36), sa.ForeignKey("hr_employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("leave_type_id", sa.String(36), sa.ForeignKey("leave_types.id", ondelete="CASCADE"), nullable=False),
        sa.Column("as_of", sa.Date, nullable=False),
        sa.Column("balance_hours", sa.Numeric(8, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("attributes", JSONB, nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("employee_id", "leave_type_id", "as_of", name="uq_leave_balance_point"),
    )
    op.create_index("ix_leave_bal_emp", "leave_balances", ["employee_id"])

    op.create_table(
        "leave_requests",
        id_col(),
        sa.Column("employee_id", sa.String(36), sa.ForeignKey("hr_employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("leave_type_id", sa.String(36), sa.ForeignKey("leave_types.id", ondelete="SET NULL")),
        sa.Column("start_date", sa.Date, nullable=False),
        sa.Column("end_date", sa.Date, nullable=False),
        sa.Column("hours_requested", sa.Numeric(8, 2), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default=sa.text("'pending'")),  # pending, approved, denied, canceled
        sa.Column("attributes", JSONB, nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_leave_req_emp", "leave_requests", ["employee_id"])

    # ===========================
    # Payroll Setup
    # ===========================
    op.create_table(
        "payroll_earnings_codes",
        id_col(),
        sa.Column("code", sa.String(16), nullable=False, unique=True),   # REG, OT, STIP, VAC-PAY
        sa.Column("description", sa.String(255), nullable=False),
        sa.Column("taxable", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("subject_to_retirement", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("attributes", JSONB, nullable=True),
        *_timestamps(),
    )

    op.create_table(
        "payroll_deduction_codes",
        id_col(),
        sa.Column("code", sa.String(16), nullable=False, unique=True),   # MED, DENT, 403B, GARN
        sa.Column("description", sa.String(255), nullable=False),
        sa.Column("pretax", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("vendor_id", sa.String(36), sa.ForeignKey("ap_vendors.id", ondelete="SET NULL")),
        sa.Column("attributes", JSONB, nullable=True),                   # calc rules, limits
        *_timestamps(),
    )

    op.create_table(
        "benefit_plans",
        id_col(),
        sa.Column("code", sa.String(16), nullable=False, unique=True),   # MED-PPO, DENT-BASE
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("vendor_id", sa.String(36), sa.ForeignKey("ap_vendors.id", ondelete="SET NULL")),
        sa.Column("attributes", JSONB, nullable=True),                   # employer/employee split, tiers
        *_timestamps(),
    )

    op.create_table(
        "employee_comp",
        id_col(),
        sa.Column("employee_id", sa.String(36), sa.ForeignKey("hr_employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_assignment_id", sa.String(36), sa.ForeignKey("hr_job_assignments.id", ondelete="SET NULL")),
        sa.Column("pay_type", sa.String(16), nullable=False, server_default=sa.text("'salary'")),  # salary/hourly/stipend
        sa.Column("annual_rate", sa.Numeric(14, 2), nullable=True),
        sa.Column("hourly_rate", sa.Numeric(14, 4), nullable=True),
        sa.Column("stipend_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("effective_start", sa.Date, nullable=False),
        sa.Column("effective_end", sa.Date, nullable=True),
        sa.Column("default_account_id", sa.String(36), sa.ForeignKey("gl_accounts.id", ondelete="SET NULL")),
        sa.Column("attributes", JSONB, nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_employee_comp_emp", "employee_comp", ["employee_id"])

    op.create_table(
        "employee_deductions",
        id_col(),
        sa.Column("employee_id", sa.String(36), sa.ForeignKey("hr_employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("deduction_code_id", sa.String(36), sa.ForeignKey("payroll_deduction_codes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("amount_type", sa.String(16), nullable=False, server_default=sa.text("'fixed'")),  # fixed/percent
        sa.Column("employee_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("employer_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("effective_start", sa.Date, nullable=False),
        sa.Column("effective_end", sa.Date, nullable=True),
        sa.Column("attributes", JSONB, nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("employee_id", "deduction_code_id", "effective_start", name="uq_emp_deduction_span"),
    )
    op.create_index("ix_emp_ded_emp", "employee_deductions", ["employee_id"])

    op.create_table(
        "employee_benefits",
        id_col(),
        sa.Column("employee_id", sa.String(36), sa.ForeignKey("hr_employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("benefit_plan_id", sa.String(36), sa.ForeignKey("benefit_plans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("coverage_tier", sa.String(32), nullable=True),        # single, ee+sp, family
        sa.Column("employee_premium", sa.Numeric(14, 2), nullable=True),
        sa.Column("employer_premium", sa.Numeric(14, 2), nullable=True),
        sa.Column("effective_start", sa.Date, nullable=False),
        sa.Column("effective_end", sa.Date, nullable=True),
        sa.Column("attributes", JSONB, nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("employee_id", "benefit_plan_id", "effective_start", name="uq_emp_benefit_span"),
    )
    op.create_index("ix_emp_benefit_emp", "employee_benefits", ["employee_id"])

    op.create_table(
        "employee_tax_profiles",
        id_col(),
        sa.Column("employee_id", sa.String(36), sa.ForeignKey("hr_employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("federal", JSONB, nullable=True),   # filing_status, dependents, extra_withholding
        sa.Column("state", JSONB, nullable=True),     # keyed by state code
        sa.Column("local", JSONB, nullable=True),
        sa.Column("effective_start", sa.Date, nullable=False),
        sa.Column("effective_end", sa.Date, nullable=True),
        sa.Column("attributes", JSONB, nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_emp_tax_emp", "employee_tax_profiles", ["employee_id"])

    # ===========================
    # Payroll Runs
    # ===========================
    op.create_table(
        "payroll_runs",
        id_col(),
        sa.Column("name", sa.String(64), nullable=True),           # e.g., FY25-BW-01
        sa.Column("frequency", sa.String(16), nullable=False, server_default=sa.text("'biweekly'")),  # weekly/biweekly/semimonthly/monthly
        sa.Column("period_start", sa.Date, nullable=False),
        sa.Column("period_end", sa.Date, nullable=False),
        sa.Column("check_date", sa.Date, nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default=sa.text("'open'")),  # open, calculated, posted, paid, void
        sa.Column("attributes", JSONB, nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("frequency", "period_start", "period_end", name="uq_run_period"),
    )

    op.create_table(
        "payroll_earnings",
        id_col(),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("payroll_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("employee_id", sa.String(36), sa.ForeignKey("hr_employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_assignment_id", sa.String(36), sa.ForeignKey("hr_job_assignments.id", ondelete="SET NULL")),
        sa.Column("earnings_code_id", sa.String(36), sa.ForeignKey("payroll_earnings_codes.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("hours", sa.Numeric(8, 2), nullable=True),
        sa.Column("rate", sa.Numeric(14, 4), nullable=True),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("account_id", sa.String(36), sa.ForeignKey("gl_accounts.id", ondelete="SET NULL")),  # expense distribution
        sa.Column("attributes", JSONB, nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_pay_earn_run", "payroll_earnings", ["run_id"])
    op.create_index("ix_pay_earn_emp", "payroll_earnings", ["employee_id"])

    op.create_table(
        "payroll_deductions_txn",
        id_col(),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("payroll_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("employee_id", sa.String(36), sa.ForeignKey("hr_employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("deduction_code_id", sa.String(36), sa.ForeignKey("payroll_deduction_codes.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("employee_amount", sa.Numeric(14, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("employer_amount", sa.Numeric(14, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("attributes", JSONB, nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_pay_ded_run", "payroll_deductions_txn", ["run_id"])
    op.create_index("ix_pay_ded_emp", "payroll_deductions_txn", ["employee_id"])

    op.create_table(
        "payroll_benefits_txn",
        id_col(),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("payroll_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("employee_id", sa.String(36), sa.ForeignKey("hr_employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("benefit_plan_id", sa.String(36), sa.ForeignKey("benefit_plans.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("employee_amount", sa.Numeric(14, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("employer_amount", sa.Numeric(14, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("attributes", JSONB, nullable=True),
        *_timestamps(),
    )
    op.create_index("ix_pay_ben_run", "payroll_benefits_txn", ["run_id"])
    op.create_index("ix_pay_ben_emp", "payroll_benefits_txn", ["employee_id"])

    op.create_table(
        "payroll_checks",
        id_col(),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("payroll_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("employee_id", sa.String(36), sa.ForeignKey("hr_employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("payment_method", sa.String(16), nullable=False, server_default=sa.text("'ach'")),  # ach, check
        sa.Column("check_no", sa.String(32), nullable=True, unique=True),
        sa.Column("gross_pay", sa.Numeric(14, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("employee_taxes", sa.Numeric(14, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("employee_deductions", sa.Numeric(14, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("net_pay", sa.Numeric(14, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("attributes", JSONB, nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("run_id", "employee_id", name="uq_check_per_run_emp"),
    )
    op.create_index("ix_pay_checks_run", "payroll_checks", ["run_id"])


def downgrade():
    # Drop in reverse dependency order
    op.drop_index("ix_pay_checks_run", table_name="payroll_checks")
    op.drop_table("payroll_checks")

    op.drop_index("ix_pay_ben_emp", table_name="payroll_benefits_txn")
    op.drop_index("ix_pay_ben_run", table_name="payroll_benefits_txn")
    op.drop_table("payroll_benefits_txn")

    op.drop_index("ix_pay_ded_emp", table_name="payroll_deductions_txn")
    op.drop_index("ix_pay_ded_run", table_name="payroll_deductions_txn")
    op.drop_table("payroll_deductions_txn")

    op.drop_index("ix_pay_earn_emp", table_name="payroll_earnings")
    op.drop_index("ix_pay_earn_run", table_name="payroll_earnings")
    op.drop_table("payroll_earnings")

    op.drop_table("payroll_runs")

    op.drop_index("ix_emp_tax_emp", table_name="employee_tax_profiles")
    op.drop_table("employee_tax_profiles")

    op.drop_index("ix_emp_benefit_emp", table_name="employee_benefits")
    op.drop_table("employee_benefits")

    op.drop_index("ix_emp_ded_emp", table_name="employee_deductions")
    op.drop_table("employee_deductions")

    op.drop_index("ix_employee_comp_emp", table_name="employee_comp")
    op.drop_table("employee_comp")

    op.drop_table("benefit_plans")
    op.drop_table("payroll_deduction_codes")
    op.drop_table("payroll_earnings_codes")

    op.drop_index("ix_leave_req_emp", table_name="leave_requests")
    op.drop_table("leave_requests")

    op.drop_index("ix_leave_bal_emp", table_name="leave_balances")
    op.drop_table("leave_balances")

    op.drop_table("leave_types")

    op.drop_index("ix_timesheet_lines_sheet", table_name="timesheet_lines")
    op.drop_table("timesheet_lines")

    op.drop_index("ix_timesheets_emp", table_name="timesheets")
    op.drop_table("timesheets")

    op.drop_table("time_codes")

    op.drop_index("ix_job_assign_school", table_name="hr_job_assignments")
    op.drop_index("ix_job_assign_emp", table_name="hr_job_assignments")
    op.drop_table("hr_job_assignments")

    op.drop_index("ix_hr_pay_steps_grade", table_name="hr_pay_steps")
    op.drop_table("hr_pay_steps")

    op.drop_table("hr_pay_grades")
    op.drop_index("ix_hr_employees_deptseg", table_name="hr_employees")
    op.drop_index("ix_hr_employees_person", table_name="hr_employees")

    op.drop_table("hr_positions")

    op.drop_index("ix_hr_employees_school", table_name="hr_employees")
    op.drop_index("ix_hr_employees_dept", table_name="hr_employees")
    op.drop_table("hr_employees")