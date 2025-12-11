from __future__ import annotations

import logging
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0283"
down_revision = "0282"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "stat_imports"

# Inline, realistic seed data
# Assumes columns: source, status, created_at, updated_at, id
SEED_ROWS = [
    {
        "id": "80e23e9c-aa96-46f0-a30e-ee78dcd9dda6",
        "source": "StateAssessment",
        "status": "success",
        "created_at": datetime(2024, 1, 1, 1, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 1, 5, tzinfo=timezone.utc),
    },
    {
        "id": "593d333f-50ac-4de7-86dd-37a1618edf1c",
        "source": "Attendance",
        "status": "success",
        "created_at": datetime(2024, 1, 1, 2, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 2, 3, tzinfo=timezone.utc),
    },
    {
        "id": "ff22b9c3-cf85-4c2c-9d8d-268397b929fb",
        "source": "Graduation",
        "status": "success",
        "created_at": datetime(2024, 1, 1, 3, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 3, 4, tzinfo=timezone.utc),
    },
    {
        "id": "790d6ef8-90a4-452a-84c7-8c098e231185",
        "source": "Enrollment",
        "status": "success",
        "created_at": datetime(2024, 1, 1, 4, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 4, 2, tzinfo=timezone.utc),
    },
    {
        "id": "db7a42da-0f81-4a62-be30-d302c7e61f06",
        "source": "Staff",
        "status": "failed",  # Example of a failed import for realism
        "created_at": datetime(2024, 1, 1, 5, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 5, 10, tzinfo=timezone.utc),
    },
]


def upgrade() -> None:
    """Seed stat_imports with a few realistic import runs.

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
