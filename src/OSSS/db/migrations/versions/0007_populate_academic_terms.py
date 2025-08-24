from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
from datetime import date


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
revision = "0007_populate_academic_terms"
down_revision = "0006_populate_behavior_codes"
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



def upgrade() -> None:

    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"

    uuid_col = (
        sa.Column("id", sa.String(36), primary_key=True,
                  server_default=text("gen_random_uuid()"))  # PG only
        if is_pg else
        sa.Column("id", sa.CHAR(36), primary_key=True)  # SQLite: no server_default
    )

    # --- Extensions (optional) ---
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")  # for gen_random_uuid()

    # Define the terms to seed (adjust to your calendar as needed)
    terms = [
        # name,        type,       start_date,        end_date
        ("Fall Semester 2025", "semester", date(2025, 8, 18), date(2025, 12, 19)),
        ("Spring Semester 2026", "semester", date(2026, 1, 6), date(2026, 5, 29)),
        ("Summer Session 2026", "session", date(2026, 6, 8), date(2026, 7, 24)),
    ]

    # Fetch all school IDs
    school_rows = bind.execute(sa.text("SELECT id FROM schools")).fetchall()
    school_ids = [row[0] for row in school_rows]

    # Idempotent insert per (school_id, name)
    insert_sql = sa.text(
        """
        INSERT INTO academic_terms (school_id, name, type, start_date, end_date)
        SELECT :school_id, :name, :type, :start_date, :end_date
        WHERE NOT EXISTS (
            SELECT 1 FROM academic_terms
            WHERE school_id = :school_id AND name = :name
        )
        """
    )

    for school_id in school_ids:
        for name, term_type, start_d, end_d in terms:
            bind.execute(
                insert_sql,
                {
                    "school_id": str(school_id),
                    "name": name,
                    "type": term_type,
                    "start_date": start_d,
                    "end_date": end_d,
                },
            )


def downgrade() -> None:
    """Remove the seeded academic terms inserted by upgrade()."""
    bind = op.get_bind()

    # Must match the names/dates in upgrade() to avoid deleting user data
    names = (
        "Fall Semester 2025",
        "Spring Semester 2026",
        "Summer Session 2026",
    )

    bind.execute(
        sa.text(
            """
            DELETE FROM academic_terms
            WHERE name = ANY(:names)
              AND start_date IN (:fall_start, :spring_start, :summer_start)
            """
        ),
        {
            "names": list(names),
            "fall_start": date(2025, 8, 18),
            "spring_start": date(2026, 1, 6),
            "summer_start": date(2026, 6, 8),
        },
    )