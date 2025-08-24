from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
from datetime import date, datetime
from typing import Dict, List, Tuple



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
revision = "0014_populate_courses"
down_revision = "0013_populate_subjects"
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
    # Ensure pgcrypto for gen_random_uuid(); harmless if already present
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")

    # Insert one course per subject, per school (via departments)
    # Idempotent: skips rows that already exist with same (school_id, subject_id, name).
    op.execute(
        sa.text(
            """
            WITH sub AS (
                SELECT
                    s.id           AS subject_id,
                    s.name         AS subject_name,
                    s.code         AS subject_code,
                    d.school_id    AS school_id
                FROM subjects s
                JOIN departments d
                  ON d.id = s.department_id
            )
            INSERT INTO courses (
                id, school_id, subject_id, name, code, credit_hours,
                created_at, updated_at
            )
            SELECT
                gen_random_uuid(), sub.school_id, sub.subject_id,
                sub.subject_name, sub.subject_code, 1.00::numeric(4,2),
                CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            FROM sub
            WHERE NOT EXISTS (
                SELECT 1
                FROM courses c
                WHERE c.school_id  = sub.school_id
                  AND c.subject_id = sub.subject_id
                  AND c.name       = sub.subject_name
            );
            """
        )
    )


def downgrade() -> None:
    # Best-effort reversal:
    # Remove only the rows that exactly match the seed pattern:
    # (course.name == subject.name) AND (course.code == subject.code OR both NULL)
    # AND (course.subject_id = subject.id) AND credit_hours = 1.00
    # This minimizes risk of deleting hand-entered courses.
    op.execute(
        sa.text(
            """
            DELETE FROM courses c
            USING subjects s
            JOIN departments d ON d.id = s.department_id
            WHERE c.subject_id = s.id
              AND c.school_id  = d.school_id
              AND c.name       = s.name
              AND (
                    (c.code IS NULL AND s.code IS NULL)
                 OR (c.code = s.code)
              )
              AND c.credit_hours = 1.00::numeric(4,2);
            """
        )
    )