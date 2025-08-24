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
revision = "0016_populate_bus_routes"
down_revision = "0015_populate_grading_periods"
branch_labels = None
depends_on = None


# Source list (name, school_name|None)
ROUTES: List[Tuple[str, Optional[str]]] = [
    ("DCG-01 — Dallas Center North", None),
    ("DCG-02 — Dallas Center South", None),
    ("DCG-03 — Grimes Northwest", None),
    ("DCG-04 — Grimes Northeast", None),
    ("DCG-05 — Grimes Southwest", None),
    ("DCG-06 — Grimes Southeast", None),
    ("DCG-07 — Rural West Loop", None),
    ("DCG-08 — Rural East Loop", None),

    # School-specific loops:
    ("DCG-09 — Heritage Elementary Loop", "Heritage Elementary"),
    ("DCG-10 — North Ridge Elementary Loop", "North Ridge Elementary"),
    ("DCG-11 — South Prairie Elementary Loop", "South Prairie Elementary"),
    ("DCG-12 — Oak View / Meadows Loop", "DC-G Oak View"),

    # Shuttles (tie to MS/HS where clear)
    ("DCG-13 — Middle School AM Shuttle", "Dallas Center-Grimes Middle School"),
    ("DCG-14 — High School AM Shuttle", "Dallas Center-Grimes High School"),

    # Transfers / activity buses (leave general)
    ("DCG-15 — PM Transfer Shuttle A", None),
    ("DCG-16 — PM Transfer Shuttle B", None),
    ("DCG-17 — Activity Bus A (After-school)", None),
    ("DCG-18 — Activity Bus B (After-school)", None),
]


def _table(name: str, *cols: sa.Column) -> sa.Table:
    return sa.table(name, *cols)


def upgrade() -> None:
    bind = op.get_bind()

    # Map school name -> id (from existing schools table)
    school_rows = bind.execute(sa.text("SELECT id, name FROM schools")).mappings().all()
    school_by_name: Dict[str, str] = {r["name"]: r["id"] for r in school_rows}

    # Already-present route names (idempotency)
    existing_names = {
        r["name"] for r in bind.execute(sa.text("SELECT name FROM bus_routes")).mappings()
    }

    # Prepare rows
    to_insert: List[Dict[str, Optional[str]]] = []
    for route_name, school_name in ROUTES:
        if route_name in existing_names:
            continue
        school_id = school_by_name.get(school_name) if school_name else None
        to_insert.append(
            {
                "id": str(uuid.uuid4()),
                "name": route_name,
                "school_id": school_id,
            }
        )

    if not to_insert:
        return

    bus_routes = _table(
        "bus_routes",
        sa.column("id", sa.String(36)),
        sa.column("name", sa.Text()),
        sa.column("school_id", sa.String(36)),
    )

    op.bulk_insert(bus_routes, to_insert)


def downgrade() -> None:
    names = [r[0] for r in ROUTES]  # all names we seeded
    op.execute(
        sa.text("DELETE FROM bus_routes WHERE name = ANY(:names)")
        .bindparams(sa.bindparam("names", value=names, type_=sa.ARRAY(sa.Text())))
    )