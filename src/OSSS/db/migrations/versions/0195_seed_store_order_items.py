from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0195"
down_revision = "0194"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "store_order_items"

# Inline seed rows for store_order_items
# Columns: order_id, product_id, quantity, price_cents, id, created_at, updated_at
# Product 29e63715-b3a3-4139-a97d-cf40cb3400fc = "Adult Football Ticket" @ 800 cents
SEED_ROWS = [
    {
        "order_id": "9d41d92b-435a-4db3-b60c-809a764ed3de",
        "product_id": "29e63715-b3a3-4139-a97d-cf40cb3400fc",
        "quantity": 1,
        "price_cents": 800,  # 1 × $8.00
        "id": "d18d3abc-b5b0-53db-97dc-c4e4357d9dcd",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
    },
    {
        "order_id": "9d41d92b-435a-4db3-b60c-809a764ed3de",
        "product_id": "29e63715-b3a3-4139-a97d-cf40cb3400fc",
        "quantity": 2,
        "price_cents": 1600,  # 2 × $8.00
        "id": "26d30975-6e55-5ef1-9b30-913216cbf93f",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
    },
    {
        "order_id": "9d41d92b-435a-4db3-b60c-809a764ed3de",
        "product_id": "29e63715-b3a3-4139-a97d-cf40cb3400fc",
        "quantity": 3,
        "price_cents": 2400,  # 3 × $8.00
        "id": "8a132299-4786-5a80-81df-b7640b60c2ac",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
    },
    {
        "order_id": "9d41d92b-435a-4db3-b60c-809a764ed3de",
        "product_id": "29e63715-b3a3-4139-a97d-cf40cb3400fc",
        "quantity": 4,
        "price_cents": 3200,  # 4 × $8.00
        "id": "b000a860-356c-5a1f-a753-0600d6f9449d",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
    },
    {
        "order_id": "9d41d92b-435a-4db3-b60c-809a764ed3de",
        "product_id": "29e63715-b3a3-4139-a97d-cf40cb3400fc",
        "quantity": 5,
        "price_cents": 4000,  # 5 × $8.00
        "id": "5bcaf71a-3070-56c0-b993-e488e4c8d62a",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
    },
]


def upgrade() -> None:
    """Load seed data for store_order_items from inline SEED_ROWS.

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
