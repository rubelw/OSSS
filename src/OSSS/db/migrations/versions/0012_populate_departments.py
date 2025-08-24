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
revision = "0012_populate_departments"
down_revision = "0011_populate_permissions"
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



# ---------------------------------------------------------------------------
# Schools we expect to seed (name, state_id, school_code)
# ---------------------------------------------------------------------------
SCHOOLS: list[tuple[str, str, str]] = [
    ("Dallas Center Elementary",           "190852000705", "436"),
    ("Dallas Center-Grimes High School",   "190852000451", "109"),
    ("Dallas Center-Grimes Middle School", "190852000453", "209"),
    ("DC-G Oak View",                      "190852002174", "218"),
    ("Heritage Elementary",                "190852002242", "437"),
    ("North Ridge Elementary",             "190852002099", "418"),
    ("South Prairie Elementary",           "190852002029", "427"),
]

# ---------------------------------------------------------------------------
# Standard departments to create per school
# (adjust as needed for your district’s taxonomy)
# ---------------------------------------------------------------------------
DEPARTMENTS: list[str] = [
    "English Language Arts",
    "Mathematics",
    "Science",
    "Social Studies",
    "World Languages",
    "Fine Arts",
    "Music",
    "Art",
    "Performing Arts",
    "Physical Education & Health",
    "Career & Technical Education",
    "Computer Science / Technology",
    "Special Education",
    "Counseling",
    "Library / Media",
    "Administration",
]


def _select_schools(conn) -> list[dict]:
    """Return list of {id, name, school_code} for the target schools."""
    codes = [code for _, _, code in SCHOOLS if code]
    names = [name for name, _, _ in SCHOOLS]

    stmt = sa.text(
        """
        SELECT id, name, school_code
        FROM schools
        WHERE school_code IN :codes OR name IN :names
        """
    ).bindparams(
        sa.bindparam("codes", expanding=True),
        sa.bindparam("names", expanding=True),
    )

    return list(conn.execute(stmt, {"codes": codes, "names": names}).mappings())


def upgrade() -> None:
    conn = op.get_bind()

    rows = _select_schools(conn)
    code_to_id = {r["school_code"]: r["id"] for r in rows if r["school_code"]}
    name_to_id = {r["name"]: r["id"] for r in rows}

    insert_stmt_pg = sa.text(
        """
        INSERT INTO departments (school_id, name)
        VALUES (:school_id, :name)
        ON CONFLICT ON CONSTRAINT uq_department_name DO NOTHING
        """
    )

    # Fallback for non-PG (rare in this project). We’ll try/except duplicates.
    insert_stmt_generic = sa.text(
        "INSERT INTO departments (school_id, name) VALUES (:school_id, :name)"
    )

    is_pg = conn.dialect.name == "postgresql"

    for school_name, _state_id, school_code in SCHOOLS:
        school_id = code_to_id.get(school_code) or name_to_id.get(school_name)
        if not school_id:
            # School not present; skip (keeps migration resilient to partial data).
            continue

        for dept_name in DEPARTMENTS:
            if is_pg:
                conn.execute(insert_stmt_pg, {"school_id": school_id, "name": dept_name})
            else:
                try:
                    conn.execute(insert_stmt_generic, {"school_id": school_id, "name": dept_name})
                except Exception:
                    # Likely a duplicate; ignore to remain idempotent.
                    pass


def downgrade() -> None:
    conn = op.get_bind()

    rows = _select_schools(conn)
    school_ids = [r["id"] for r in rows]

    if not school_ids:
        return

    delete_stmt = sa.text(
        """
        DELETE FROM departments
        WHERE school_id IN :school_ids
          AND name IN :dept_names
        """
    ).bindparams(
        sa.bindparam("school_ids", expanding=True),
        sa.bindparam("dept_names", expanding=True),
    )

    conn.execute(delete_stmt, {"school_ids": school_ids, "dept_names": DEPARTMENTS})