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
revision = "0009_create_finance_tables"
down_revision = "0008_create_cmms_iwms_tables"
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
    if is_pg:
        conn.execute(sa.text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))

    def id_col():
        return sa.Column(
            "id", sa.String(36), primary_key=True,
            server_default=text("gen_random_uuid()") if is_pg else None,
        )

    # =========================
    # Master: Segments & COA
    # =========================
    # Segment types typical for K-12: fund, function, program, project, location, object, etc.
    op.create_table(
        "gl_segments",
        id_col(),
        sa.Column("type", sa.String(24), nullable=False),       # fund/function/program/project/location/object/...
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("parent_id", sa.String(36), sa.ForeignKey("gl_segments.id", ondelete="SET NULL")),
        sa.Column("active", sa.Boolean, nullable=False, server_default=text("true")),
        sa.Column("attributes", JSONB(), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("type", "code", name="uq_gl_segments_type_code"),
    )
    op.create_index("ix_gl_segments_type", "gl_segments", ["type"])

    # GL accounts (postable nodes in your chart)
    op.create_table(
        "gl_accounts",
        id_col(),
        sa.Column("number", sa.String(64), nullable=False, unique=True),  # full concatenated account string
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("natural_class", sa.String(16), nullable=True),  # asset/liability/equity/revenue/expense
        sa.Column("is_postable", sa.Boolean, nullable=False, server_default=text("true")),
        sa.Column("active", sa.Boolean, nullable=False, server_default=text("true")),
        sa.Column("segments_json", JSONB(), nullable=True),        # optional: ordered segment IDs/values
        sa.Column("attributes", JSONB(), nullable=True),
        *_timestamps(),
    )

    # Optional normalized mapping between accounts and segments (if you prefer not to rely on segments_json)
    op.create_table(
        "gl_account_segments",
        id_col(),
        sa.Column("account_id", sa.String(36), sa.ForeignKey("gl_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("segment_id", sa.String(36), sa.ForeignKey("gl_segments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position", sa.Integer, nullable=False),  # 1=fund, 2=function, etc. (district-defined)
        *_timestamps(),
        sa.UniqueConstraint("account_id", "position", name="uq_gl_acctseg_account_pos"),
    )
    op.create_index("ix_gl_acctseg_acct", "gl_account_segments", ["account_id"])
    op.create_index("ix_gl_acctseg_seg", "gl_account_segments", ["segment_id"])

    # AP Vendors (commonly used by Finance, Payroll, Purchasing)
    op.create_table(
        "ap_vendors",
        id_col(),
        sa.Column("vendor_no", sa.String(32), nullable=True, unique=True),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("tax_id", sa.String(32), nullable=True),
        sa.Column("remit_to", JSONB(), nullable=True),   # address/contact
        sa.Column("contact", JSONB(), nullable=True),    # phone/email/etc
        sa.Column("active", sa.Boolean, nullable=False, server_default=text("true")),
        sa.Column("attributes", JSONB(), nullable=True),
        *_timestamps(),
    )

    # =========================
    # Fiscal Structure
    # =========================
    op.create_table(
        "fiscal_years",
        id_col(),
        sa.Column("code", sa.String(16), nullable=False, unique=True),  # e.g., FY2025
        sa.Column("start_date", sa.Date, nullable=False),
        sa.Column("end_date", sa.Date, nullable=False),
        sa.Column("is_closed", sa.Boolean, nullable=False, server_default=text("false")),
        sa.Column("attributes", JSONB(), nullable=True),
        *_timestamps(),
    )

    op.create_table(
        "fiscal_periods",
        id_col(),
        sa.Column("fiscal_year_id", sa.String(36), sa.ForeignKey("fiscal_years.id", ondelete="CASCADE"), nullable=False),
        sa.Column("period_no", sa.Integer, nullable=False),    # 1..13
        sa.Column("name", sa.String(32), nullable=False),      # Jul, Aug, Period 13, etc.
        sa.Column("start_date", sa.Date, nullable=False),
        sa.Column("end_date", sa.Date, nullable=False),
        sa.Column("is_closed", sa.Boolean, nullable=False, server_default=text("false")),
        sa.Column("attributes", JSONB(), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("fiscal_year_id", "period_no", name="uq_year_period"),
    )
    op.create_index("ix_periods_year", "fiscal_periods", ["fiscal_year_id"])

    # =========================
    # Journal Entries
    # =========================
    op.create_table(
        "journal_entries",
        id_col(),
        sa.Column("fiscal_year_id", sa.String(36), sa.ForeignKey("fiscal_years.id", ondelete="SET NULL")),
        sa.Column("fiscal_period_id", sa.String(36), sa.ForeignKey("fiscal_periods.id", ondelete="SET NULL")),
        sa.Column("entry_date", sa.Date, nullable=False),
        sa.Column("batch_no", sa.String(32), nullable=True),
        sa.Column("source", sa.String(16), nullable=True),      # GL, AP, AR, PR, JE
        sa.Column("reference", sa.String(64), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default=text("'open'")),  # open/posted/void
        sa.Column("posted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("posted_by_user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("attributes", JSONB(), nullable=True),
        *_timestamps(),
        sa.Index("ix_je_period", "fiscal_period_id"),
        sa.Index("ix_je_date", "entry_date"),
    )

    op.create_table(
        "journal_entry_lines",
        id_col(),
        sa.Column("journal_entry_id", sa.String(36), sa.ForeignKey("journal_entries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("line_no", sa.Integer, nullable=False),
        sa.Column("account_id", sa.String(36), sa.ForeignKey("gl_accounts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("debit", sa.Numeric(14, 2), nullable=False, server_default=text("0")),
        sa.Column("credit", sa.Numeric(14, 2), nullable=False, server_default=text("0")),
        sa.Column("memo", sa.String(255), nullable=True),
        sa.Column("segments_override", JSONB(), nullable=True),  # if line-level segments differ from account defaults
        sa.Column("attributes", JSONB(), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("journal_entry_id", "line_no", name="uq_je_line_seq"),
    )
    op.create_index("ix_jel_account", "journal_entry_lines", ["account_id"])
    op.create_index("ix_jel_je", "journal_entry_lines", ["journal_entry_id"])

    # =========================
    # Balances / Trial Balance
    # =========================
    op.create_table(
        "gl_account_balances",
        id_col(),
        sa.Column("account_id", sa.String(36), sa.ForeignKey("gl_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("fiscal_period_id", sa.String(36), sa.ForeignKey("fiscal_periods.id", ondelete="CASCADE"), nullable=False),
        sa.Column("begin_balance", sa.Numeric(16, 2), nullable=False, server_default=text("0")),
        sa.Column("debit_total", sa.Numeric(16, 2), nullable=False, server_default=text("0")),
        sa.Column("credit_total", sa.Numeric(16, 2), nullable=False, server_default=text("0")),
        sa.Column("end_balance", sa.Numeric(16, 2), nullable=False, server_default=text("0")),
        sa.Column("attributes", JSONB(), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("account_id", "fiscal_period_id", name="uq_balance_acct_period"),
    )
    op.create_index("ix_balances_acct", "gl_account_balances", ["account_id"])
    op.create_index("ix_balances_period", "gl_account_balances", ["fiscal_period_id"])


def downgrade():
    op.drop_index("ix_balances_period", table_name="gl_account_balances")
    op.drop_index("ix_balances_acct", table_name="gl_account_balances")
    op.drop_table("gl_account_balances")

    op.drop_index("ix_jel_je", table_name="journal_entry_lines")
    op.drop_index("ix_jel_account", table_name="journal_entry_lines")
    op.drop_table("journal_entry_lines")

    # indexes on journal_entries were inline
    op.drop_table("journal_entries")

    op.drop_index("ix_periods_year", table_name="fiscal_periods")
    op.drop_table("fiscal_periods")
    op.drop_table("fiscal_years")

    op.drop_table("ap_vendors")

    op.drop_index("ix_gl_acctseg_seg", table_name="gl_account_segments")
    op.drop_index("ix_gl_acctseg_acct", table_name="gl_account_segments")
    op.drop_table("gl_account_segments")

    op.drop_table("gl_accounts")

    op.drop_index("ix_gl_segments_type", table_name="gl_segments")
    op.drop_table("gl_segments")