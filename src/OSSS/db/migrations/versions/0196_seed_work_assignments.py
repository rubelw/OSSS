from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0196"
down_revision = "0195"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "work_assignments"

# Inline seed rows for work_assignments
# Columns:
#   event_id, worker_id, stipend_cents, status,
#   assigned_at, checked_in_at, completed_at,
#   id, created_at, updated_at
SEED_ROWS = [
    {
        "event_id": "13e28612-f86c-5753-8964-2ed13f37a8b4",
        "worker_id": "d5228b09-d142-4827-8c15-7c35920a84eb",
        "stipend_cents": 5000,  # $50.00
        "status": "declined",
        "assigned_at": "2024-01-01T01:00:00Z",
        "checked_in_at": "2024-01-01T01:00:00Z",
        "completed_at": "2024-01-01T01:00:00Z",
        "id": "114a3acb-ffa9-5912-b128-d27d558e7796",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
    },
    {
        "event_id": "13e28612-f86c-5753-8964-2ed13f37a8b4",
        "worker_id": "d5228b09-d142-4827-8c15-7c35920a84eb",
        "stipend_cents": 7500,  # $75.00
        "status": "confirmed",
        "assigned_at": "2024-01-01T02:00:00Z",
        "checked_in_at": "2024-01-01T02:00:00Z",
        "completed_at": "2024-01-01T02:00:00Z",
        "id": "cbde0516-708f-5e52-ae82-4559865fa81a",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
    },
    {
        "event_id": "13e28612-f86c-5753-8964-2ed13f37a8b4",
        "worker_id": "d5228b09-d142-4827-8c15-7c35920a84eb",
        "stipend_cents": 10000,  # $100.00
        "status": "pending",
        "assigned_at": "2024-01-01T03:00:00Z",
        "checked_in_at": "2024-01-01T03:00:00Z",
        "completed_at": "2024-01-01T03:00:00Z",
        "id": "68ca497c-e76c-504f-b510-52d1e402070d",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
    },
    {
        "event_id": "13e28612-f86c-5753-8964-2ed13f37a8b4",
        "worker_id": "d5228b09-d142-4827-8c15-7c35920a84eb",
        "stipend_cents": 12500,  # $125.00
        "status": "completed",
        "assigned_at": "2024-01-01T04:00:00Z",
        "checked_in_at": "2024-01-01T04:00:00Z",
        "completed_at": "2024-01-01T04:00:00Z",
        "id": "e53c25ce-8cb4-5273-b096-1b0f8a9d4e66",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
    },
    {
        "event_id": "13e28612-f86c-5753-8964-2ed13f37a8b4",
        "worker_id": "d5228b09-d142-4827-8c15-7c35920a84eb",
        "stipend_cents": 15000,  # $150.00
        "status": "completed",
        "assigned_at": "2024-01-01T05:00:00Z",
        "checked_in_at": "2024-01-01T05:00:00Z",
        "completed_at": "2024-01-01T05:00:00Z",
        "id": "24d7609d-ab65-56e7-8bb7-4e0d85d18f0c",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
    },
]


def upgrade() -> None:
    """Load seed data for work_assignments from inline SEED_ROWS.

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
        row = {col.name: raw_row[col.name] for col in table.columns if col.name in raw_row}

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

    log.info("Inserted %s rows into %s from inline SEED_ROWS", inserted, TABLE_NAME)


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
