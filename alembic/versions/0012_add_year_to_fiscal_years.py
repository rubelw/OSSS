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
revision = "0012_add_year_to_fiscal_years"
down_revision = "0011_create_hr_position_asgnmnt"
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
    # 1) add the column (nullable first so backfill won’t fail)
    op.add_column("fiscal_years", sa.Column("year", sa.Integer(), nullable=True))

    # 2) optional backfill: derive FY from start_date (common July–June assumption)
    #    FY = start_date.year + 1 if start month >= 7 else start_date.year
    op.execute("""
        UPDATE fiscal_years
           SET year = EXTRACT(YEAR FROM start_date)::int
                     + CASE WHEN EXTRACT(MONTH FROM start_date) >= 7 THEN 1 ELSE 0 END
        WHERE year IS NULL
    """)

    # 3) (optional) add a partial unique index so only non-null years must be unique
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_fiscal_years_year ON fiscal_years(year) WHERE year IS NOT NULL")

def downgrade():
    op.execute("DROP INDEX IF EXISTS uq_fiscal_years_year")
    op.drop_column("fiscal_years", "year")