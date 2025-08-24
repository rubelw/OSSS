from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
from datetime import date, datetime



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
revision = "0008_populate_standardized_tests"
down_revision = "0007_populate_academic_terms"
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
    standardized_tests = sa.table(
        "standardized_tests",
        sa.column("id", sa.String),
        sa.column("name", sa.Text),
        sa.column("subject", sa.Text),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    now = datetime.utcnow()
    op.bulk_insert(
        standardized_tests,
        [
            {
                "id": str(uuid.uuid4()),
                "name": "ISASP",
                "subject": "Mathematics; English–Language Arts (Reading & Writing); Science",
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": str(uuid.uuid4()),
                "name": "Iowa Assessments",
                "subject": (
                    "Vocabulary; Reading Comprehension; Spelling; Capitalization; "
                    "Punctuation; Usage & Expression; Math (Concepts, Problem Solving, Computation); "
                    "Social Studies; Maps & Diagrams; Reference Materials; Word Analysis; Listening"
                ),
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": str(uuid.uuid4()),
                "name": "ITED",
                "subject": (
                    "Vocabulary; Reading Comprehension; Language Skills; Spelling; "
                    "Math Concepts & Problem Solving; Analysis of Social Studies; "
                    "Analysis of Science; Information Sources"
                ),
                "created_at": now,
                "updated_at": now,
            },
        ],
    )

def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM standardized_tests WHERE name IN ('ISASP','Iowa Assessments','ITED')"
        )
    )