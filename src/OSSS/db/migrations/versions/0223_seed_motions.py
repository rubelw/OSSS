from __future__ import annotations

import csv  # kept for consistency with other migrations, even if unused
import logging
import os

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0223"
down_revision = "0222"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "motions"
CSV_FILE = None  # seeding from inline data instead of CSV

# Columns:
# agenda_item_id, text, moved_by_id, seconded_by_id,
# passed, tally_for, tally_against, tally_abstain,
# id, created_at, updated_at
SEED_ROWS = [
    {
        "agenda_item_id": "ca321d07-eec1-539e-a9f4-17f7d2533683",
        "text": "Motion to approve the meeting agenda as presented.",
        "moved_by_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "seconded_by_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "passed": True,
        "tally_for": 5,
        "tally_against": 0,
        "tally_abstain": 0,
        "id": "329bbcc8-402b-5e1e-902a-0b29edbaa36d",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
    },
    {
        "agenda_item_id": "ca321d07-eec1-539e-a9f4-17f7d2533683",
        "text": "Motion to approve the minutes from the December regular board meeting.",
        "moved_by_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "seconded_by_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "passed": True,
        "tally_for": 5,
        "tally_against": 0,
        "tally_abstain": 0,
        "id": "b5f38146-c5c4-59dc-9b5e-070ca3f909e2",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
    },
    {
        "agenda_item_id": "ca321d07-eec1-539e-a9f4-17f7d2533683",
        "text": "Motion to adopt the revised student activity eligibility policy.",
        "moved_by_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "seconded_by_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "passed": False,
        "tally_for": 2,
        "tally_against": 3,
        "tally_abstain": 0,
        "id": "31bd4f3b-74e5-5d7c-bea3-b395a8dd8cb2",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
    },
    {
        "agenda_item_id": "ca321d07-eec1-539e-a9f4-17f7d2533683",
        "text": "Motion to approve the FY 2024–25 general fund budget amendment.",
        "moved_by_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "seconded_by_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "passed": True,
        "tally_for": 4,
        "tally_against": 1,
        "tally_abstain": 0,
        "id": "77838ca7-4c03-5c35-92cc-808cd24549df",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
    },
    {
        "agenda_item_id": "ca321d07-eec1-539e-a9f4-17f7d2533683",
        "text": "Motion to adjourn the meeting.",
        "moved_by_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "seconded_by_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "passed": True,
        "tally_for": 5,
        "tally_against": 0,
        "tally_abstain": 0,
        "id": "b5a1edcc-f544-5f0d-acb4-43d7d302afae",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
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
            log.warning(
                "Invalid boolean for %s.%s: %r; using NULL", TABLE_NAME, col.name, raw
            )
            return None
        return bool(raw)

    # Otherwise, pass raw through and let DB cast (UUID, timestamptz, text, etc.)
    return raw


def upgrade() -> None:
    """Load seed data for motions from inline SEED_ROWS (no CSV)."""
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
