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
revision = "0006_populate_behavior_codes"
down_revision = "0005_populate_schools_table"
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

CODES = [
    ("TARD", "Tardy to class"),
    ("SKIP", "Skipping class / Unexcused absence"),
    ("DRSG", "Dress code violation"),
    ("DISR", "Disruptive behavior in class"),
    ("DISO", "Disobedience / Insubordination"),
    ("INAP", "Inappropriate language / gestures"),
    ("FGT",  "Fighting / Physical aggression"),
    ("HRAS", "Harassment / Bullying"),
    ("THRT", "Threat / Intimidation"),
    ("VAND", "Vandalism / Property damage"),
    ("THEF", "Theft"),
    ("TOB",  "Tobacco possession/use"),
    ("DRUG", "Drugs / Alcohol possession or use"),
    ("WEAP", "Weapon possession"),
    ("CHEA", "Academic dishonesty / Cheating"),
    ("TECH", "Technology misuse (e.g., inappropriate internet use)"),
    ("OTHR", "Other (uncategorized behavior)"),
]

def upgrade() -> None:
    conn = op.get_bind()
    stmt = sa.text(
        """
        INSERT INTO behavior_codes (code, description)
        VALUES (:code, :description)
        ON CONFLICT (code) DO UPDATE
        SET description = EXCLUDED.description,
            updated_at = NOW()
        """
    )
    for code, desc in CODES:
        conn.execute(stmt, {"code": code, "description": desc})


def downgrade() -> None:
    # Remove only the seeded codes (safe even if some didn’t exist)
    codes_sql_list = ", ".join([sa.text(f":c{i}").text for i in range(len(CODES))])
    params = {f"c{i}": code for i, (code, _) in enumerate(CODES)}
    op.execute(sa.text(f"DELETE FROM behavior_codes WHERE code IN ({codes_sql_list})"), params)
