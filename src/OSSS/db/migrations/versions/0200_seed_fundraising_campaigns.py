from __future__ import annotations

import csv  # kept for consistency with other migrations, though unused here
import logging
import os  # kept for consistency

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0200"
down_revision = "0199"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "fundraising_campaigns"
CSV_FILE = os.path.join(os.path.dirname(__file__), "csv", f"{TABLE_NAME}.csv")

# Inline, realistic seed data for fundraising_campaigns
# All rows use the same school_id as provided in your sample:
#   af33eba3-d881-554e-9b43-2a7ea376e1f0
SEED_ROWS = [
    {
        "title": "Scoreboard Upgrade Drive",
        "goal_cents": 2_500_000,  # $25,000
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "id": "19624444-0ee7-5e2d-97a8-536a42e951b7",
    },
    {
        "title": "Uniform Refresh Campaign",
        "goal_cents": 1_500_000,  # $15,000
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "id": "41542a6a-0859-50ad-8a7a-dab6b1d9032d",
    },
    {
        "title": "Band Trip to State",
        "goal_cents": 1_000_000,  # $10,000
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "id": "ab05a999-1b15-5a11-abb7-99e1803b1214",
    },
    {
        "title": "STEM Lab Equipment Fund",
        "goal_cents": 2_000_000,  # $20,000
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "id": "c379137f-d4a4-59e4-a8c7-3cbc05203465",
    },
    {
        "title": "Activity Fund Booster",
        "goal_cents": 500_000,  # $5,000
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "id": "7c098495-570f-5163-900c-f9e1147d3440",
    },
]


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion from CSV string to appropriate Python value.

    Kept for consistency with other migrations, though not used with inline data.
    """
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
    """Load seed data for fundraising_campaigns from inline SEED_ROWS.

    Each row is inserted inside an explicit nested transaction (SAVEPOINT)
    so a failing row won't abort the whole migration transaction.
    """
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(TABLE_NAME):
        log.warning("Table %s does not exist; skipping seed", TABLE_NAME)
        return

    metadata = sa.MetaData()
    table = sa.Table(TABLE_NAME, metadata, autoload_with=bind)

    inserted = 0
    for raw_row in SEED_ROWS:
        # Only include columns that actually exist on the table
        row = {col.name: raw_row[col.name] for col in table.columns if col.name in raw_row}

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

    log.info(
        "Inserted %s rows into %s from inline SEED_ROWS",
        inserted,
        TABLE_NAME,
    )


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
