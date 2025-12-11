from __future__ import annotations

import csv
import logging
import os
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0294"
down_revision = "0293"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "team_messages"
CSV_FILE = os.path.join(os.path.dirname(__file__), "csv", f"{TABLE_NAME}.csv")

# Inline seed data: content, created_at, updated_at, team_id, id
SEED_ROWS = [
    {
        "id": "4464d5ad-75c5-5302-9ca3-cdfc19d6f8c0",
        "team_id": "ee268bc5-47ec-59b2-b5bb-00492928ca1f",
        "content": "Welcome to the OSSS implementation channel. We’ll use this space for daily updates and blockers.",
        "created_at": datetime(2024, 1, 1, 1, 0, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 1, 0, 0, tzinfo=timezone.utc),
    },
    {
        "id": "8b55e5e0-9716-53e0-8758-7c2cd95f01cb",
        "team_id": "ee268bc5-47ec-59b2-b5bb-00492928ca1f",
        "content": "Reminder: data migration dry run is scheduled for Thursday at 3:30 PM. Please confirm your availability.",
        "created_at": datetime(2024, 1, 1, 2, 0, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 2, 0, 0, tzinfo=timezone.utc),
    },
    {
        "id": "52dd4c95-e659-5767-b889-98fd74621807",
        "team_id": "ee268bc5-47ec-59b2-b5bb-00492928ca1f",
        "content": "Action item: log any student registration issues you see in the OSSS issue tracker by end of day.",
        "created_at": datetime(2024, 1, 1, 3, 0, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 3, 0, 0, tzinfo=timezone.utc),
    },
    {
        "id": "5c163b6a-b1dc-548a-91d1-df4e4a0a44f1",
        "team_id": "ee268bc5-47ec-59b2-b5bb-00492928ca1f",
        "content": "Today’s focus: verify payroll, attendance, and enrollment syncs in the sandbox environment.",
        "created_at": datetime(2024, 1, 1, 4, 0, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 4, 0, 0, tzinfo=timezone.utc),
    },
    {
        "id": "37879934-2419-5e81-91d2-7bd72b131e60",
        "team_id": "ee268bc5-47ec-59b2-b5bb-00492928ca1f",
        "content": "Thanks everyone for jumping on the late-afternoon deployment call—great progress on the initial rollout.",
        "created_at": datetime(2024, 1, 1, 5, 0, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 5, 0, 0, tzinfo=timezone.utc),
    },
]


def _coerce_value(col: sa.Column, raw):
    """Inline seeds are already typed correctly; just return the value."""
    return raw


def upgrade() -> None:
    """Seed team_messages with inline data instead of a CSV file."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(TABLE_NAME):
        log.warning("Table %s does not exist; skipping seed", TABLE_NAME)
        return

    metadata = sa.MetaData()
    table = sa.Table(TABLE_NAME, metadata, autoload_with=bind)

    inserted = 0
    for raw_row in SEED_ROWS:
        row = {}

        # Only populate columns that exist on the table
        for col in table.columns:
            if col.name not in raw_row:
                continue
            row[col.name] = _coerce_value(col, raw_row[col.name])

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
