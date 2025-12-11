from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0159"
down_revision = "0158"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "meal_transactions"

# Inline seed rows for meal_transactions
# Columns: account_id, transacted_at, amount, description,
#          created_at, updated_at, id
# Updated to use realistic meal transaction descriptions.
SEED_ROWS = [
    {
        "account_id": "1ef0fce9-96b8-5c8e-a3c7-e93c1476c354",
        "transacted_at": "2024-01-01T01:00:00Z",
        "amount": 1,
        "description": "Breakfast meal charge",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
        "id": "da40e155-f3a4-557f-9e1e-4912aa1389e9",
    },
    {
        "account_id": "1ef0fce9-96b8-5c8e-a3c7-e93c1476c354",
        "transacted_at": "2024-01-01T02:00:00Z",
        "amount": 2,
        "description": "Lunch meal charge",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
        "id": "61f53a91-2d71-5ce7-a824-2e2f3f28f6a5",
    },
    {
        "account_id": "1ef0fce9-96b8-5c8e-a3c7-e93c1476c354",
        "transacted_at": "2024-01-01T03:00:00Z",
        "amount": 3,
        "description": "Cafeteria snack purchase",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
        "id": "d7e87612-c4df-51bc-883d-8cf75a6acd2b",
    },
    {
        "account_id": "1ef0fce9-96b8-5c8e-a3c7-e93c1476c354",
        "transacted_at": "2024-01-01T04:00:00Z",
        "amount": 4,
        "description": "Parent deposit – online payment",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
        "id": "a6101c0d-4b9b-5f52-be26-7f7a95eeab52",
    },
    {
        "account_id": "1ef0fce9-96b8-5c8e-a3c7-e93c1476c354",
        "transacted_at": "2024-01-01T05:00:00Z",
        "amount": 5,
        "description": "Account adjustment – prior balance correction",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
        "id": "7ec9fa91-5509-5c89-9ec9-c8b8d1ea347a",
    },
]


def upgrade() -> None:
    """Load seed data for meal_transactions from inline SEED_ROWS.

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
