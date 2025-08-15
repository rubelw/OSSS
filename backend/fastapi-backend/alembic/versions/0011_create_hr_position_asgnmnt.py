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
revision = "0011_create_hr_position_asgnmnt"
down_revision = "0010_create_payroll_hr_tables"
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
    op.create_table(
        "hr_position_assignments",
        sa.Column("id", sa.String(36), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("employee_id", sa.String(36), sa.ForeignKey("hr_employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position_id", sa.String(36), sa.ForeignKey("hr_positions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("start_date", sa.Date),
        sa.Column("end_date", sa.Date),
        sa.Column("percent", sa.Numeric(5, 2)),
        sa.Column("funding_split", JSONB(), nullable=True),  # e.g. {"fundA": 0.5, "fundB": 0.5}
        *_timestamps(),
        sa.UniqueConstraint("employee_id", "position_id", "start_date", "end_date", name="uq_hr_pos_assign_span"),
    )
    op.create_index("ix_hr_pos_assign_employee", "hr_position_assignments", ["employee_id"])
    op.create_index("ix_hr_pos_assign_position", "hr_position_assignments", ["position_id"])


def downgrade():
    op.drop_index("ix_hr_pos_assign_position", table_name="hr_position_assignments")
    op.drop_index("ix_hr_pos_assign_employee", table_name="hr_position_assignments")
    op.drop_table("hr_position_assignments")