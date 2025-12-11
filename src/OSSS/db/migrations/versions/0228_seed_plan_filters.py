from __future__ import annotations

import csv  # kept for consistency with other migrations, even if unused
import logging
import os

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0228"
down_revision = "0227"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "plan_filters"
CSV_FILE = None  # seeding from inline data instead of CSV


# Inline seed data with realistic values:
# plan_id, name, criteria (JSON), id, created_at, updated_at
SEED_ROWS = [
    {
        # High-level view of all in-progress and not-started goals in the strategic plan
        "plan_id": "7f2eb6b4-2c3e-4c78-9d7a-90bb2b67e21d",
        "name": "All Strategic Goals – In Progress / Not Started",
        "criteria": {
            "entity_types": ["goal"],
            "statuses": ["in_progress", "not_started"],
            "include_archived": False,
        },
        "id": "b063336f-57dc-53fc-9b49-b3169ef59348",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
    },
]


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion from seed values to appropriate Python/DB values."""
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
            log.warning("Invalid boolean for %s.%s: %r; using NULL", TABLE_NAME, col.name, raw)
            return None
        return bool(raw)

    # JSON/UUID/text/etc. are passed through and cast by the DB
    return raw


def upgrade() -> None:
    """Load seed data for plan_filters from inline SEED_ROWS (no CSV read)."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(TABLE_NAME):
        log.warning("Table %s does not exist; skipping seed", TABLE_NAME)
        return

    metadata = sa.MetaData()
    table = sa.Table(TABLE_NAME, metadata, autoload_with=bind)

    rows = SEED_ROWS
    if not rows:
        log.info("No inline seed rows defined for %s", TABLE_NAME)
        return

    inserted = 0
    for raw_row in rows:
        row: dict[str, object] = {}

        for col in table.columns:
            if col.name not in raw_row:
                continue

            raw_val = raw_row[col.name]
            value = _coerce_value(col, raw_val)
            row[col.name] = value

        if not row:
            continue

        # Explicit nested transaction (SAVEPOINT) so a bad row doesn't kill the migration
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

    log.info("Inserted %s inline seed rows into %s", inserted, TABLE_NAME)


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
