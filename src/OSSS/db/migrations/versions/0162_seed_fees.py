from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0162"
down_revision = "0161"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "fees"

# Inline seed rows for fees
# Columns: school_id, name, amount, created_at, updated_at, id
# Updated to use realistic fee names.
SEED_ROWS = [
    {
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "name": "General registration fee",
        "amount": 1,
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
        "id": "13ebc36e-527c-5df9-b532-6f77c52157b3",
    },
    {
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "name": "Instructional materials / textbook fee",
        "amount": 2,
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
        "id": "0efa23c5-613d-53b6-a644-881a5f737c07",
    },
    {
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "name": "Technology / device usage fee",
        "amount": 3,
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
        "id": "21547b78-b2d5-5bd1-91bc-060ab08e7e4a",
    },
    {
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "name": "Athletics participation fee",
        "amount": 4,
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
        "id": "326966e4-5add-5f15-b4ed-d2ee1dc955f4",
    },
    {
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "name": "Field trip / activity fee",
        "amount": 5,
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
        "id": "baf3ceda-12d7-5d01-8477-a690acaa9f78",
    },
]


def upgrade() -> None:
    """Load seed data for fees from inline SEED_ROWS.

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
        row: dict[str, object] = {}
        for col in table.columns:
            if col.name in raw_row:
                row[col.name] = raw_row[col.name]

        if not row:
            continue

        # Explicit nested transaction (SAVEPOINT)
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
