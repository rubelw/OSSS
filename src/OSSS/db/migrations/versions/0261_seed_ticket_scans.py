from __future__ import annotations

import logging
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0261"
down_revision = "0260"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "ticket_scans"

TICKET_ID = "026ebaa1-aaed-56e7-9fdf-7fbf70a072d1"
SCANNED_BY_USER_ID = "de036046-aeed-4e84-960c-07ca8f9b99b9"

# Inline seed rows with realistic scan data
SEED_ROWS = [
    {
        "id": "ddab33d8-a3bb-517c-9036-c06c8da63821",
        "ticket_id": TICKET_ID,
        "scanned_by_user_id": SCANNED_BY_USER_ID,
        "scanned_at": datetime(2024, 1, 15, 13, 5, tzinfo=timezone.utc),
        "result": "valid",
        "location": "Main Entrance - Door A",
        "meta": {
            "scanner_id": "HANDHELD-01",
            "direction": "entry",
            "source": "barcode",
        },
        "created_at": datetime(2024, 1, 15, 13, 5, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 15, 13, 5, tzinfo=timezone.utc),
    },
    {
        "id": "53166411-3308-58d1-bc58-a103185da982",
        "ticket_id": TICKET_ID,
        "scanned_by_user_id": SCANNED_BY_USER_ID,
        "scanned_at": datetime(2024, 1, 15, 13, 7, tzinfo=timezone.utc),
        "result": "duplicate",
        "location": "Main Entrance - Door A",
        "meta": {
            "scanner_id": "HANDHELD-01",
            "direction": "entry",
            "reason": "ticket_already_used",
        },
        "created_at": datetime(2024, 1, 15, 13, 7, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 15, 13, 7, tzinfo=timezone.utc),
    },
    {
        "id": "2a393cc7-7bee-5ef5-9f68-befae2ed3764",
        "ticket_id": TICKET_ID,
        "scanned_by_user_id": SCANNED_BY_USER_ID,
        "scanned_at": datetime(2024, 1, 15, 13, 30, tzinfo=timezone.utc),
        "result": "valid",
        "location": "Gym Entrance - Door C",
        "meta": {
            "scanner_id": "WALL-READER-03",
            "direction": "entry",
            "source": "qr_code",
        },
        "created_at": datetime(2024, 1, 15, 13, 30, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 15, 13, 30, tzinfo=timezone.utc),
    },
    {
        "id": "4a73d299-5b8c-5052-9348-21f031846c16",
        "ticket_id": TICKET_ID,
        "scanned_by_user_id": SCANNED_BY_USER_ID,
        "scanned_at": datetime(2024, 1, 15, 16, 0, tzinfo=timezone.utc),
        "result": "exit",
        "location": "Main Entrance - Door B",
        "meta": {
            "scanner_id": "HANDHELD-02",
            "direction": "exit",
        },
        "created_at": datetime(2024, 1, 15, 16, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 15, 16, 0, tzinfo=timezone.utc),
    },
    {
        "id": "b3dcab1c-93a0-5892-b3ec-dba6cc35ba1f",
        "ticket_id": TICKET_ID,
        "scanned_by_user_id": SCANNED_BY_USER_ID,
        "scanned_at": datetime(2024, 1, 16, 12, 0, tzinfo=timezone.utc),
        "result": "invalid",
        "location": "Main Entrance - Door A",
        "meta": {
            "scanner_id": "HANDHELD-01",
            "direction": "entry",
            "reason": "event_expired",
        },
        "created_at": datetime(2024, 1, 16, 12, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 16, 12, 0, tzinfo=timezone.utc),
    },
]


def upgrade() -> None:
    """Seed ticket_scans with inline rows.

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
