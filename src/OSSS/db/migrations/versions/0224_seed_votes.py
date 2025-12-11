from __future__ import annotations

import csv  # kept for consistency with other migrations, even if unused
import logging
import os

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0224"
down_revision = "0223"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "votes"
CSV_FILE = None  # seeding from inline data instead of CSV


# Inline seed data:
# motion_id, voter_id, value, id, created_at, updated_at
#
# Using the motions seeded in 0223:
#   329bbcc8-402b-5e1e-902a-0b29edbaa36d  (approve agenda, passed)
#   b5f38146-c5c4-59dc-9b5e-070ca3f909e2  (approve minutes, passed)
#   31bd4f3b-74e5-5d7c-bea3-b395a8dd8cb2  (policy change, failed)
#   77838ca7-4c03-5c35-92cc-808cd24549df  (budget amendment, passed)
#   b5a1edcc-f544-5f0d-acb4-43d7d302afae  (adjourn, passed)
SEED_ROWS = [
    {
        "motion_id": "329bbcc8-402b-5e1e-902a-0b29edbaa36d",
        "voter_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "value": "yes",
        "id": "06a2dc98-3834-5a67-92af-9c4b12b19856",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
    },
    {
        "motion_id": "b5f38146-c5c4-59dc-9b5e-070ca3f909e2",
        "voter_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "value": "yes",
        "id": "9f945928-ec98-53c0-ad97-8c25d8b58dd4",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
    },
    {
        "motion_id": "31bd4f3b-74e5-5d7c-bea3-b395a8dd8cb2",
        "voter_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "value": "no",
        "id": "8a83db26-96dc-5562-a82c-7d4fc8ddac6d",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
    },
    {
        "motion_id": "77838ca7-4c03-5c35-92cc-808cd24549df",
        "voter_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "value": "yes",
        "id": "e73ccb48-92b8-5165-832b-71eb94b533d9",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
    },
    {
        "motion_id": "b5a1edcc-f544-5f0d-acb4-43d7d302afae",
        "voter_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "value": "yes",
        "id": "477beaa5-4855-532c-bf45-d1be083db362",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
    },
]


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion from inline seed values to appropriate Python/DB values."""
    if raw == "" or raw is None:
        return None

    t = col.type

    # Boolean handling (if you later add any bool columns to votes)
    if isinstance(t, sa.Boolean):
        if isinstance(raw, str):
            v = raw.strip().lower()
            if v in ("true", "t", "1", "yes", "y"):
                return True
            if v in ("false", "f", "0", "no", "n"):
                return False
            log.warning(
                "Invalid boolean for %s.%s: %r; using NULL", TABLE_NAME, col.name, raw
            )
            return None
        return bool(raw)

    # Otherwise, let the DB cast (UUID, timestamp, text, etc.)
    return raw


def upgrade() -> None:
    """Load seed data for votes from inline SEED_ROWS (no CSV)."""
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
