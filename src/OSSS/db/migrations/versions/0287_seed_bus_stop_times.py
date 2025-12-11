from __future__ import annotations

import logging
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0287"
down_revision = "0286"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "bus_stop_times"

# Inline seed rows
# Columns: route_id, stop_id, arrival_time, departure_time, created_at, updated_at, id
SEED_ROWS = [
    {
        # AM pickup at neighborhood stop
        "id": "54aee847-53a5-59c2-a2d1-b88b9a057868",
        "route_id": "dc004672-2936-552e-831b-4e2516959a9e",
        "stop_id": "c6715e2f-3d54-5193-913a-112e1faadb14",
        "arrival_time": "07:05:00",
        "departure_time": "07:05:00",
        "created_at": datetime(2024, 8, 1, 1, 0, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 8, 1, 1, 0, 0, tzinfo=timezone.utc),
    },
    {
        # AM pickup on a late-start day
        "id": "d727d002-c487-57fd-988b-9dfe5d178830",
        "route_id": "dc004672-2936-552e-831b-4e2516959a9e",
        "stop_id": "c6715e2f-3d54-5193-913a-112e1faadb14",
        "arrival_time": "08:35:00",
        "departure_time": "08:35:00",
        "created_at": datetime(2024, 8, 1, 2, 0, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 8, 1, 2, 0, 0, tzinfo=timezone.utc),
    },
    {
        # Midday shuttle stop (e.g., program or shared campus)
        "id": "7ea8ca40-bbbf-598d-a17e-c90dbe38674e",
        "route_id": "dc004672-2936-552e-831b-4e2516959a9e",
        "stop_id": "c6715e2f-3d54-5193-913a-112e1faadb14",
        "arrival_time": "11:30:00",
        "departure_time": "11:30:00",
        "created_at": datetime(2024, 8, 1, 3, 0, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 8, 1, 3, 0, 0, tzinfo=timezone.utc),
    },
    {
        # Early-dismissal run
        "id": "079340bc-f4e7-57da-9e92-8a43cebc8192",
        "route_id": "dc004672-2936-552e-831b-4e2516959a9e",
        "stop_id": "c6715e2f-3d54-5193-913a-112e1faadb14",
        "arrival_time": "13:15:00",
        "departure_time": "13:15:00",
        "created_at": datetime(2024, 8, 1, 4, 0, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 8, 1, 4, 0, 0, tzinfo=timezone.utc),
    },
    {
        # Regular PM drop-off
        "id": "e7eada10-3cd0-5dcf-867a-415e6f262b1b",
        "route_id": "dc004672-2936-552e-831b-4e2516959a9e",
        "stop_id": "c6715e2f-3d54-5193-913a-112e1faadb14",
        "arrival_time": "15:25:00",
        "departure_time": "15:25:00",
        "created_at": datetime(2024, 8, 1, 5, 0, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 8, 1, 5, 0, 0, tzinfo=timezone.utc),
    },
]


def _coerce_value(col: sa.Column, raw):
    """For inline seeds we already provide appropriately-typed values."""
    return raw


def upgrade() -> None:
    """Seed bus_stop_times with realistic example rows."""
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

        # Only include keys that match actual columns
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

    log.info("Inserted %s rows into %s", inserted, TABLE_NAME)


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
