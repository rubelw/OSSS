from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "tags"

SEED_ROWS = [
    {
        "id": "2bb58942-5512-4ab3-948d-4a7afc8961db",
        "name": "Math",
        "category": "subject",
        "color": "blue",
    },
    {
        "id": "56e17b60-889a-44f1-b8f8-857234dde9ba",
        "name": "ELA",
        "category": "subject",
        "color": "red",
    },
    {
        "id": "51696612-765d-4bac-a117-1cc48a4f3779",
        "name": "Urgent",
        "category": "priority",
        "color": "orange",
    },
    {
        "id": "2c41936c-45c4-48f9-bef0-a7d6ffa3569f",
        "name": "Family",
        "category": "other",
        "color": "green",
    },
    {
        "id": "e2167149-313e-43b5-93da-fa207b6e0b17",
        "name": "Facilities",
        "category": "other",
        "color": "purple",
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

    # Otherwise, pass raw through and let DB cast
    return raw


def upgrade() -> None:
    """Load seed data for tags from inline SEED_ROWS.

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
            raw_val = None

            if col.name in raw_row:
                raw_val = raw_row[col.name]
            elif col.name == "label" and "name" in raw_row:
                # Map legacy "name" field into the new NOT NULL "label" column
                raw_val = raw_row["name"]
            else:
                # Let server defaults handle timestamps etc.
                continue

            value = _coerce_value(col, raw_val)
            row[col.name] = value

        if not row:
            continue

        # Explicit nested transaction (SAVEPOINT)
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

    log.info(
        "Inserted %s rows into %s from inline seed data",
        inserted,
        TABLE_NAME,
    )


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
