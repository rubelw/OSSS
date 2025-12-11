from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0194"
down_revision = "0193"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "store_orders"

# Inline seed rows for store_orders
# Columns: customer_id, status, notes, metadata, id, created_at, updated_at
SEED_ROWS = [
    {
        "customer_id": "60606e85-af53-527a-b335-4eb05db4e239",
        "status": "paid",
        "notes": "Online order for two adult football tickets.",
        "metadata": {"channel": "online", "order_number": "SO-1001"},
        "id": "9d41d92b-435a-4db3-b60c-809a764ed3de",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
    },
    {
        "customer_id": "a0ee268a-1368-5c31-863a-742ccbf8ad83",
        "status": "paid",
        "notes": "Concessions bundle purchased at varsity game.",
        "metadata": {"channel": "in_person", "order_number": "SO-1002"},
        "id": "5ce72896-c9ff-4b30-aa3f-31768c526141",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
    },
    {
        "customer_id": "3ffbdaa5-c8a0-52da-a1d8-4b666b7b421f",
        "status": "paid",
        "notes": "Spirit wear (hoodie and t-shirt) paid in full.",
        "metadata": {"channel": "online", "order_number": "SO-1003"},
        "id": "0d94c7db-8950-4d34-a394-00961f99d5fd",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
    },
    {
        "customer_id": "c490f222-8120-50f5-a64f-41f3cb4b948c",
        "status": "paid",
        "notes": "Family activity passes for fall semester.",
        "metadata": {"channel": "office", "order_number": "SO-1004"},
        "id": "204c8781-0bd3-445e-aa9c-4f0b866cb87c",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
    },
    {
        "customer_id": "9e04b0af-7019-58b7-97a4-6b33cfda8c40",
        "status": "pending",
        "notes": "Shopping cart created; awaiting payment confirmation.",
        "metadata": {"channel": "online", "order_number": "SO-1005"},
        "id": "7a4e218d-f22e-4a6a-a313-f86d030434cc",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
    },
]


def upgrade() -> None:
    """Load seed data for store_orders from inline SEED_ROWS.

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
