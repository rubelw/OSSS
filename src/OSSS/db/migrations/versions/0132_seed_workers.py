from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0132"
down_revision = "0131"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "workers"

# Inline seed data (replaces CSV)
ROWS = [
    {
        "first_name": "Worker1",
        "last_name": "Facilities",
        "created_at": "2024-01-01T01:00:00Z",
        "id": "d5228b09-d142-4827-8c15-7c35920a84eb",
        "updated_at": "2024-01-01T01:00:00Z",
    },
    {
        "first_name": "Worker2",
        "last_name": "Facilities",
        "created_at": "2024-01-01T02:00:00Z",
        "id": "c88b8f22-8810-4385-a3a5-757720f1350e",
        "updated_at": "2024-01-01T02:00:00Z",
    },
    {
        "first_name": "Worker3",
        "last_name": "Facilities",
        "created_at": "2024-01-01T03:00:00Z",
        "id": "37fc5c47-4260-4756-8d6a-39bef042e5f0",
        "updated_at": "2024-01-01T03:00:00Z",
    },
    {
        "first_name": "Worker4",
        "last_name": "Facilities",
        "created_at": "2024-01-01T04:00:00Z",
        "id": "289a8bb8-06b1-4080-819e-1587b9ad4119",
        "updated_at": "2024-01-01T04:00:00Z",
    },
    {
        "first_name": "Worker5",
        "last_name": "Facilities",
        "created_at": "2024-01-01T05:00:00Z",
        "id": "12b2a9a3-b668-492f-9385-35f1d05051f0",
        "updated_at": "2024-01-01T05:00:00Z",
    },
]


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion from inline seed rows to appropriate Python value."""
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

    # Otherwise, let the DB cast (UUID, timestamptz, etc.)
    return raw


def upgrade() -> None:
    """Seed fixed workers rows inline (no CSV file)."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(TABLE_NAME):
        log.warning("Table %s does not exist; skipping seed", TABLE_NAME)
        return

    metadata = sa.MetaData()
    table = sa.Table(TABLE_NAME, metadata, autoload_with=bind)

    if not ROWS:
        log.info("No inline rows for %s; skipping", TABLE_NAME)
        return

    inserted = 0
    for raw_row in ROWS:
        row: dict[str, object] = {}

        for col in table.columns:
            if col.name not in raw_row:
                continue
            raw_val = raw_row[col.name]
            row[col.name] = _coerce_value(col, raw_val)

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

    log.info("Inserted %s inline rows into %s", inserted, TABLE_NAME)


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
