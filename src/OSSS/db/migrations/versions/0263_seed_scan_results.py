from __future__ import annotations

import logging
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0263"
down_revision = "0262"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "scan_results"

TICKET_ID = "026ebaa1-aaed-56e7-9fdf-7fbf70a072d1"

# Inline seed rows with realistic scan result data
SEED_ROWS = [
    {
        "id": "8f015159-2e55-5be2-9089-46bd4dbbc447",
        "ok": False,
        "ticket_id": TICKET_ID,
        "status": "invalid_ticket",
        "message": "Ticket not found or has been revoked.",
        "created_at": datetime(2024, 1, 15, 13, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 15, 13, 0, tzinfo=timezone.utc),
    },
    {
        "id": "77e8518a-2b4d-5437-b4b4-29bf6a73b0ea",
        "ok": True,
        "ticket_id": TICKET_ID,
        "status": "success_entry",
        "message": "Ticket accepted. Entry granted at Main Entrance - Door A.",
        "created_at": datetime(2024, 1, 15, 13, 5, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 15, 13, 5, tzinfo=timezone.utc),
    },
    {
        "id": "aeb931e0-2a1f-5807-a386-53dbd7c579f2",
        "ok": False,
        "ticket_id": TICKET_ID,
        "status": "duplicate_scan",
        "message": "Ticket has already been used for entry at this event.",
        "created_at": datetime(2024, 1, 15, 13, 7, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 15, 13, 7, tzinfo=timezone.utc),
    },
    {
        "id": "c51086f7-ff7f-5448-ae1d-a7e690ee42ed",
        "ok": True,
        "ticket_id": TICKET_ID,
        "status": "success_exit",
        "message": "Ticket scanned for exit at Main Entrance - Door B.",
        "created_at": datetime(2024, 1, 15, 16, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 15, 16, 0, tzinfo=timezone.utc),
    },
    {
        "id": "7f081e02-d6a4-5171-b756-d12b32027237",
        "ok": False,
        "ticket_id": TICKET_ID,
        "status": "event_expired",
        "message": "Event has ended. Ticket can no longer be used for entry.",
        "created_at": datetime(2024, 1, 16, 12, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 16, 12, 0, tzinfo=timezone.utc),
    },
]


def upgrade() -> None:
    """Seed scan_results with inline rows.

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
