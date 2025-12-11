from __future__ import annotations

import csv  # kept for consistency with other migrations, even if unused
import logging
import os

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0222"
down_revision = "0221"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "attendance"
CSV_FILE = None  # seeding from inline data instead of CSV

# Columns: id, meeting_id, user_id, status, arrived_at, left_at
SEED_ROWS = [
    {
        "id": "99fe92e7-b133-5aa4-a789-777db165734f",
        "meeting_id": "89ab8c9b-8c20-5b36-95db-e4e7e0a5e3b4",
        "user_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "status": "present",
        "arrived_at": "2024-01-01T00:55:00Z",
        "left_at": "2024-01-01T02:15:00Z",
    },
    {
        "id": "f9662771-4486-5acd-8989-bb01ee9ebd08",
        "meeting_id": "89ab8c9b-8c20-5b36-95db-e4e7e0a5e3b4",
        "user_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "status": "present",
        "arrived_at": "2024-01-01T01:00:00Z",
        "left_at": "2024-01-01T02:10:00Z",
    },
    {
        "id": "92755a1a-5e94-59e5-b936-72798dd9a3c2",
        "meeting_id": "89ab8c9b-8c20-5b36-95db-e4e7e0a5e3b4",
        "user_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "status": "present",
        "arrived_at": "2024-01-01T01:05:00Z",
        "left_at": "2024-01-01T02:00:00Z",
    },
    {
        "id": "00c91974-ffff-5f37-8ac9-be513d00653d",
        "meeting_id": "89ab8c9b-8c20-5b36-95db-e4e7e0a5e3b4",
        "user_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "status": "present",
        "arrived_at": "2024-01-01T00:50:00Z",
        "left_at": "2024-01-01T02:20:00Z",
    },
    {
        "id": "a5f68432-08f1-5a34-a93e-af782e00fc6c",
        "meeting_id": "89ab8c9b-8c20-5b36-95db-e4e7e0a5e3b4",
        "user_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "status": "present",
        "arrived_at": "2024-01-01T00:58:00Z",
        "left_at": "2024-01-01T02:05:00Z",
    },
]


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion from inline seed values to appropriate Python/DB values."""
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

    # Otherwise, pass raw through and let DB cast (UUID, timestamptz, text, etc.)
    return raw


def upgrade() -> None:
    """Load seed data for attendance from inline SEED_ROWS (no CSV)."""
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
