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
revision = "0009_populate_attendance_codes"
down_revision = "0008_populate_standardized_tests"
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
    attendance_codes = sa.table(
        "attendance_codes",
        sa.column("code", sa.Text),
        sa.column("description", sa.Text),
        sa.column("is_present", sa.Boolean),
        sa.column("is_excused", sa.Boolean),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )

    now = datetime.utcnow()

    op.bulk_insert(
        attendance_codes,
        [
            {"code": "P", "description": "Present", "is_present": True, "is_excused": False, "created_at": now, "updated_at": now},
            {"code": "A-EXC", "description": "Absent, Excused", "is_present": False, "is_excused": True, "created_at": now, "updated_at": now},
            {"code": "A-UNX", "description": "Absent, Unexcused", "is_present": False, "is_excused": False, "created_at": now, "updated_at": now},
            {"code": "T-EXC", "description": "Tardy, Excused", "is_present": True, "is_excused": True, "created_at": now, "updated_at": now},
            {"code": "T-UNX", "description": "Tardy, Unexcused", "is_present": True, "is_excused": False, "created_at": now, "updated_at": now},
            {"code": "ED-EXC", "description": "Early Dismissal, Excused", "is_present": True, "is_excused": True, "created_at": now, "updated_at": now},
            {"code": "ED-UNX", "description": "Early Dismissal, Unexcused", "is_present": True, "is_excused": False, "created_at": now, "updated_at": now},
            {"code": "SA", "description": "School Activity (counts as Present per policy)", "is_present": True, "is_excused": True, "created_at": now, "updated_at": now},
            {"code": "MED", "description": "Medical (district/state rules determine excused status)", "is_present": False, "is_excused": True, "created_at": now, "updated_at": now},
            {"code": "ISS", "description": "In-School Suspension (mapped per policy)", "is_present": False, "is_excused": True, "created_at": now, "updated_at": now},
            {"code": "OSS", "description": "Out-of-School Suspension (mapped per policy)", "is_present": False, "is_excused": True, "created_at": now, "updated_at": now},
            {"code": "FAM", "description": "Approved Family/Personal (excused)", "is_present": False, "is_excused": True, "created_at": now, "updated_at": now},
            {"code": "UN", "description": "Unverified/No reason provided (unexcused)", "is_present": False, "is_excused": False, "created_at": now, "updated_at": now},
            {"code": "QUA", "description": "State-directed Quarantine", "is_present": False, "is_excused": True, "created_at": now, "updated_at": now},
        ],
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM attendance_codes WHERE code IN "
            "('P','A-EXC','A-UNX','T-EXC','T-UNX','ED-EXC','ED-UNX','SA','MED','ISS','OSS','FAM','UN','QUA')"
        )
    )