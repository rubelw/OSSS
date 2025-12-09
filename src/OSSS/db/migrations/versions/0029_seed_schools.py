from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "schools"

SEED_ROWS = [
    {
        "organization_id": "c201e5e9-60c0-466f-8f63-aecbf868c420",
        "name": "DCG High School",
        "school_code": "DCGHS",
        "nces_school_id": "191008001531",
        "building_code": "HS-01",
        "type": "High School",
        "timezone": "America/Chicago",
        "id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
    },
    {
        "organization_id": "c201e5e9-60c0-466f-8f63-aecbf868c420",
        "name": "DCG Middle School",
        "school_code": "DCGMS",
        "nces_school_id": "191008001532",
        "building_code": "MS-01",
        "type": "Middle School",
        "timezone": "America/Chicago",
        "id": "119caaef-ef97-5364-b179-388e108bd40d",
    },
    {
        "organization_id": "c201e5e9-60c0-466f-8f63-aecbf868c420",
        "name": "South Prairie Elementary School",
        "school_code": "SPES",
        "nces_school_id": "191008001535",
        "building_code": "ES-03",
        "type": "Elementary School",
        "timezone": "America/Chicago",
        "id": "b122fcb4-2864-593c-9b05-2188ef296db4",
    },
    {
        "organization_id": "c201e5e9-60c0-466f-8f63-aecbf868c420",
        "name": "Heritage Elementary School",
        "school_code": "HES",
        "nces_school_id": "191008001533",
        "building_code": "ES-01",
        "type": "Elementary School",
        "timezone": "America/Chicago",
        "id": "df4b1423-d755-5c7f-a0ba-6908de77f61b",
    },
    {
        "organization_id": "c201e5e9-60c0-466f-8f63-aecbf868c420",
        "name": "North Ridge Elementary School",
        "school_code": "NRES",
        "nces_school_id": "191008001534",
        "building_code": "ES-02",
        "type": "Elementary School",
        "timezone": "America/Chicago",
        "id": "634b8058-d620-5a5c-86b5-c0794d3a3b73",
    },
]


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion from inline value to appropriate DB value."""
    if raw == "" or raw is None:
        return None

    t = col.type

    # Boolean needs special handling because SQLAlchemy is strict
    if isinstance(t, sa.Boolean):
        if isinstance(raw, str):
            v = raw.strip().lower()
            if v in ("true", "t", "1", "yes", "y"):
                return True
            if v in ("false", "f", "0", "no", "n"):
                return False
            log.warning(
                "Invalid boolean for %s.%s: %r; using NULL",
                TABLE_NAME,
                col.name,
                raw,
            )
            return None
        return bool(raw)

    # Otherwise, pass raw through and let DB cast (dates, enums, etc.)
    return raw


def upgrade() -> None:
    """Load seed data for schools from inline SEED_ROWS.

    Each row is inserted inside an explicit nested transaction (SAVEPOINT)
    so a failing row won't abort the whole migration transaction.
    """
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(TABLE_NAME):
        log.warning("Table %s does not exist; skipping seed", TABLE_NAME)
        return

    if not SEED_ROWS:
        log.info("No seed rows defined for %s; skipping", TABLE_NAME)
        return

    metadata = sa.MetaData()
    table = sa.Table(TABLE_NAME, metadata, autoload_with=bind)

    inserted = 0
    for raw_row in SEED_ROWS:
        row = {}

        # Only include columns that actually exist on the table
        for col in table.columns:
            if col.name not in raw_row:
                continue
            raw_val = raw_row[col.name]
            value = _coerce_value(col, raw_val)
            row[col.name] = value

        if not row:
            continue

        nested = bind.begin_nested()
        try:
            bind.execute(table.insert().values(**row))
            nested.commit()
            inserted += 1
        except (IntegrityError, DataError, StatementError) as exc:
            nested.rollback()
            log.warning(
                "Skipping row for %s due to error: %s. Row: %s",
                TABLE_NAME,
                exc,
                raw_row,
            )

    log.info("Inserted %s rows into %s from inline seed data", inserted, TABLE_NAME)


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
