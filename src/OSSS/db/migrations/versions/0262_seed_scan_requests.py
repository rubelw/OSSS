from __future__ import annotations

import logging
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0262"
down_revision = "0261"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "scan_requests"

# Inline seed rows with realistic QR codes and locations
SEED_ROWS = [
    {
        "id": "648a1064-ffd3-414d-8358-cb7123059434",
        "qr_code": "SCAN-REQUEST-ENTRY-DOOR-A-20240115T130000Z",
        "location": "Main Entrance - Door A",
        "created_at": datetime(2024, 1, 15, 13, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 15, 13, 0, tzinfo=timezone.utc),
    },
    {
        "id": "62800516-1d1d-4c40-a3c5-43149734845d",
        "qr_code": "SCAN-REQUEST-GYM-DOOR-C-20240115T131500Z",
        "location": "Gym Entrance - Door C",
        "created_at": datetime(2024, 1, 15, 13, 15, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 15, 13, 15, tzinfo=timezone.utc),
    },
    {
        "id": "a8dfede9-ca14-4ca2-ab84-0201843f147f",
        "qr_code": "SCAN-REQUEST-AUDITORIUM-LOBBY-20240115T133000Z",
        "location": "Auditorium Lobby - East",
        "created_at": datetime(2024, 1, 15, 13, 30, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 15, 13, 30, tzinfo=timezone.utc),
    },
    {
        "id": "f8eb9ae6-570f-4d10-bb93-5d531c1f70ba",
        "qr_code": "SCAN-REQUEST-STUDENT-ENTRANCE-20240115T134500Z",
        "location": "Student Entrance - South",
        "created_at": datetime(2024, 1, 15, 13, 45, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 15, 13, 45, tzinfo=timezone.utc),
    },
    {
        "id": "cfbc1937-7eb9-421c-994f-76579b420b0b",
        "qr_code": "SCAN-REQUEST-PARKING-LOT-GATE-20240115T140000Z",
        "location": "Parking Lot Gate - West",
        "created_at": datetime(2024, 1, 15, 14, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 15, 14, 0, tzinfo=timezone.utc),
    },
]


def upgrade() -> None:
    """Seed scan_requests with inline rows.

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
