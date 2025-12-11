from __future__ import annotations

import logging
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0275"
down_revision = "0274"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "export_runs"

# Inline seed rows with realistic export history
SEED_ROWS = [
    {
        "id": "0fe2dd7c-95f7-4803-8f89-065bb22d83be",
        "export_name": "student_roster_nightly",
        "ran_at": datetime(2024, 1, 1, 1, 0, tzinfo=timezone.utc),
        "status": "success",
        "file_uri": "s3://district-data-exports/student_roster/2024/01/01/student_roster_2024-01-01T01-00-00Z.csv",
        "error": None,
        "created_at": datetime(2024, 1, 1, 1, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 1, 0, tzinfo=timezone.utc),
    },
    {
        "id": "f73fddf0-f79b-4efe-af50-ea8885069555",
        "export_name": "daily_attendance_export",
        "ran_at": datetime(2024, 1, 1, 2, 0, tzinfo=timezone.utc),
        "status": "success",
        "file_uri": "s3://district-data-exports/attendance/2024/01/01/daily_attendance_2024-01-01.csv",
        "error": None,
        "created_at": datetime(2024, 1, 1, 2, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 2, 0, tzinfo=timezone.utc),
    },
    {
        "id": "a620e173-0306-48b1-8e04-efda1260a6a8",
        "export_name": "gradebook_snapshot",
        "ran_at": datetime(2024, 1, 1, 3, 0, tzinfo=timezone.utc),
        "status": "failed",
        "file_uri": None,
        "error": "Upstream SIS timeout while loading gradebook data.",
        "created_at": datetime(2024, 1, 1, 3, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 3, 10, tzinfo=timezone.utc),
    },
    {
        "id": "2b8c984f-9f43-40dd-b7dd-d98a93c75e9e",
        "export_name": "state_reporting_student_detail",
        "ran_at": datetime(2024, 1, 1, 4, 0, tzinfo=timezone.utc),
        "status": "success",
        "file_uri": "s3://district-data-exports/state_reporting/2024/01/01/student_detail_2024-01-01.zip",
        "error": None,
        "created_at": datetime(2024, 1, 1, 4, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 4, 5, tzinfo=timezone.utc),
    },
    {
        "id": "b5cc1399-ce89-4503-99b7-f926d1f17131",
        "export_name": "billing_transportation_routes",
        "ran_at": datetime(2024, 1, 1, 5, 0, tzinfo=timezone.utc),
        "status": "success",
        "file_uri": "s3://district-data-exports/transportation/2024/01/01/routes_2024-01-01.csv",
        "error": None,
        "created_at": datetime(2024, 1, 1, 5, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 5, 0, tzinfo=timezone.utc),
    },
]


def upgrade() -> None:
    """Seed export_runs with inline rows.

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
