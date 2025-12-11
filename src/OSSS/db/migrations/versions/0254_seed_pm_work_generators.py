from __future__ import annotations

import logging
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0254"
down_revision = "0253"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "pm_work_generators"

# Single plan we’re attaching generators to
PM_PLAN_ID = "c0f3ca9f-e837-5dae-b69c-c30a2beb1c62"

# Seed rows with more realistic lookahead windows and timestamps
SEED_ROWS = [
    {
        "id": "694313fd-aa79-5460-8530-da8b6a07f4b6",
        "pm_plan_id": PM_PLAN_ID,
        "lookahead_days": 7,  # 1 week
        "last_generated_at": datetime(2024, 8, 1, 8, 0, tzinfo=timezone.utc),
        "attributes": {"description": "Generate work for the upcoming week"},
        "created_at": datetime(2024, 7, 1, 8, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 8, 1, 8, 0, tzinfo=timezone.utc),
    },
    {
        "id": "b7801282-60fd-507d-8102-316accaa9b19",
        "pm_plan_id": PM_PLAN_ID,
        "lookahead_days": 14,  # 2 weeks
        "last_generated_at": datetime(2024, 8, 1, 8, 5, tzinfo=timezone.utc),
        "attributes": {"description": "Generate work for the next two weeks"},
        "created_at": datetime(2024, 7, 1, 8, 5, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 8, 1, 8, 5, tzinfo=timezone.utc),
    },
    {
        "id": "82d7e198-66f2-51cd-91b3-c32414300d3e",
        "pm_plan_id": PM_PLAN_ID,
        "lookahead_days": 30,  # roughly one month
        "last_generated_at": datetime(2024, 8, 1, 8, 10, tzinfo=timezone.utc),
        "attributes": {"description": "Generate work for the next 30 days"},
        "created_at": datetime(2024, 7, 1, 8, 10, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 8, 1, 8, 10, tzinfo=timezone.utc),
    },
    {
        "id": "f25a79a7-c914-5238-b3e1-ee5f68a4c7c5",
        "pm_plan_id": PM_PLAN_ID,
        "lookahead_days": 60,  # 2 months
        "last_generated_at": datetime(2024, 8, 1, 8, 15, tzinfo=timezone.utc),
        "attributes": {"description": "Generate work for the next 60 days"},
        "created_at": datetime(2024, 7, 1, 8, 15, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 8, 1, 8, 15, tzinfo=timezone.utc),
    },
    {
        "id": "c393fb41-ad48-532a-83b7-5c5db7af3192",
        "pm_plan_id": PM_PLAN_ID,
        "lookahead_days": 90,  # quarter
        "last_generated_at": datetime(2024, 8, 1, 8, 20, tzinfo=timezone.utc),
        "attributes": {"description": "Generate work for the next quarter"},
        "created_at": datetime(2024, 7, 1, 8, 20, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 8, 1, 8, 20, tzinfo=timezone.utc),
    },
]


def upgrade() -> None:
    """Seed pm_work_generators with inline rows.

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
