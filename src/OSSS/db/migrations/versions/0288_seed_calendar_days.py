from __future__ import annotations

import csv  # kept for consistency, though unused now
import logging
import os
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0288"
down_revision = "0287_1"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "calendar_days"
CSV_FILE = os.path.join(os.path.dirname(__file__), "csv", f"{TABLE_NAME}.csv")

# Inline seed data
# Columns: calendar_id, date, day_type, notes, created_at, updated_at, id
SEED_ROWS = [
    {
        # First student day of the term
        "id": "83359939-d536-539f-a95b-622991c9e8ca",
        "calendar_id": "06ccb9f6-6bd6-5e3a-86c4-bbdf6a17c36b",
        "date": "2024-01-02",
        "day_type": "instructional",
        "notes": "First student day of the spring semester.",
        "created_at": datetime(2024, 1, 1, 1, 0, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 1, 0, 0, tzinfo=timezone.utc),
    },
    {
        # Regular school day
        "id": "48e97768-2abc-5fee-8ca4-fb4e0c54d1f0",
        "calendar_id": "06ccb9f6-6bd6-5e3a-86c4-bbdf6a17c36b",
        "date": "2024-01-03",
        "day_type": "instructional",
        "notes": "Regular instructional day.",
        "created_at": datetime(2024, 1, 1, 2, 0, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 2, 0, 0, tzinfo=timezone.utc),
    },
    {
        # Teacher workday / PD
        "id": "4879ec24-576a-57c9-af10-87a46b88cf5e",
        "calendar_id": "06ccb9f6-6bd6-5e3a-86c4-bbdf6a17c36b",
        "date": "2024-01-04",
        "day_type": "teacher_workday",
        "notes": "Teacher workday and professional learning – no students.",
        "created_at": datetime(2024, 1, 1, 3, 0, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 3, 0, 0, tzinfo=timezone.utc),
    },
    {
        # Holiday
        "id": "c1bd217f-337e-5a47-852b-c62ddef01a54",
        "calendar_id": "06ccb9f6-6bd6-5e3a-86c4-bbdf6a17c36b",
        "date": "2024-01-05",
        "day_type": "holiday",
        "notes": "District closed for observed holiday.",
        "created_at": datetime(2024, 1, 1, 4, 0, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 4, 0, 0, tzinfo=timezone.utc),
    },
    {
        # Weather / emergency closure
        "id": "a9f40c62-7247-50df-89c5-35d1f52ef5b9",
        "calendar_id": "06ccb9f6-6bd6-5e3a-86c4-bbdf6a17c36b",
        "date": "2024-01-06",
        "day_type": "weather",
        "notes": "School canceled due to winter weather.",
        "created_at": datetime(2024, 1, 1, 5, 0, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 5, 0, 0, tzinfo=timezone.utc),
    },
]


def _coerce_value(col: sa.Column, raw):
    """For inline seeds we already provide appropriately-typed values."""
    return raw


def upgrade() -> None:
    """Seed calendar_days with realistic example rows."""
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
