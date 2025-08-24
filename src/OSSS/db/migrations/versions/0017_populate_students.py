from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
from datetime import date, datetime, timedelta
from typing import Dict, List, Tuple, Optional



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
revision = "0017_populate_students"
down_revision = "0016_populate_bus_routes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Define a lightweight table for bulk_insert
    students_tbl = sa.table(
        "students",
        sa.column("student_number", sa.Text),
        sa.column("graduation_year", sa.Integer),
    )

    rows = []
    for year in range(2019, 2036):  # inclusive 2019..2035
        # Mark as seed data; F/M denotes a female/male placeholder counterpart
        rows.append(
            {"student_number": f"SEED-{year}-F", "graduation_year": year}
        )
        rows.append(
            {"student_number": f"SEED-{year}-M", "graduation_year": year}
        )

    # Insert rows; id/created_at/updated_at are provided by server defaults
    op.bulk_insert(students_tbl, rows)


def downgrade() -> None:
    # Safely remove only the seed rows we added
    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            DELETE FROM students
            WHERE student_number LIKE 'SEED-%'
              AND graduation_year BETWEEN :start_yr AND :end_yr
            """
        ),
        {"start_yr": 2019, "end_yr": 2035},
    )