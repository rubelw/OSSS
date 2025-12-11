from __future__ import annotations

import logging
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0255"
down_revision = "0254"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "space_reservations"


# Inline seed rows with more realistic data
SEED_ROWS = [
    {
        "id": "8b8ed8aa-30fe-5050-9ade-88e93d1f204c",
        "space_id": "8b3aa9d0-8d1e-5d94-8c02-9eb3a38e7e88",
        "booked_by_user_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "start_at": datetime(2024, 1, 8, 15, 0, tzinfo=timezone.utc),
        "end_at": datetime(2024, 1, 8, 16, 0, tzinfo=timezone.utc),
        "purpose": "Weekly staff meeting",
        "status": "confirmed",
        "setup": {
            "layout": "conference",
            "seats": 10,
            "equipment": ["projector", "whiteboard"],
        },
        "attributes": {
            "notes": "Recurring Monday staff meeting; coffee service requested."
        },
        "created_at": datetime(2023, 12, 15, 10, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2023, 12, 15, 10, 30, tzinfo=timezone.utc),
    },

]


def upgrade() -> None:
    """Seed space_reservations with inline rows.

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
        row = {
            col.name: raw_row[col.name]
            for col in table.columns
            if col.name in raw_row
        }

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

    log.info("Inserted %s rows into %s", inserted, TABLE_NAME)


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
