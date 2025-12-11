from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0191"
down_revision = "0190"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "order_line_items"

# Inline seed rows for order_line_items
# Columns:
# order_id, ticket_type_id, quantity, unit_price_cents,
# created_at, updated_at, id
SEED_ROWS = [
    {
        # Two adult tickets at $12.00 each
        "order_id": "c4f8bc7f-a2ef-5587-b637-901a3096acec",
        "ticket_type_id": "4408eb5e-fcb7-5e86-885a-a08b5bf3015c",
        "quantity": 2,
        "unit_price_cents": 1200,
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
        "id": "49c86835-b59a-53a9-b8d4-e3b494a271c8",
    },
    {
        # One student ticket at $8.00
        "order_id": "c4f8bc7f-a2ef-5587-b637-901a3096acec",
        "ticket_type_id": "4408eb5e-fcb7-5e86-885a-a08b5bf3015c",
        "quantity": 1,
        "unit_price_cents": 800,
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
        "id": "a29a75cb-78d2-55ac-967d-59bf8cf1a167",
    },
    {
        # Three concession vouchers at $5.00 each
        "order_id": "c4f8bc7f-a2ef-5587-b637-901a3096acec",
        "ticket_type_id": "4408eb5e-fcb7-5e86-885a-a08b5bf3015c",
        "quantity": 3,
        "unit_price_cents": 500,
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
        "id": "1a3a7192-5260-553b-80a9-82ea0c48bd71",
    },
    {
        # One VIP upgrade at $15.00
        "order_id": "c4f8bc7f-a2ef-5587-b637-901a3096acec",
        "ticket_type_id": "4408eb5e-fcb7-5e86-885a-a08b5bf3015c",
        "quantity": 1,
        "unit_price_cents": 1500,
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
        "id": "dedd86c1-d282-5fc4-95ea-e4c0677e7c41",
    },
    {
        # Four parking passes at $3.00 each
        "order_id": "c4f8bc7f-a2ef-5587-b637-901a3096acec",
        "ticket_type_id": "4408eb5e-fcb7-5e86-885a-a08b5bf3015c",
        "quantity": 4,
        "unit_price_cents": 300,
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
        "id": "d7e14081-b89e-5cf9-9ee8-01cfe4d5dc66",
    },
]


def upgrade() -> None:
    """Load seed data for order_line_items from inline SEED_ROWS.

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
        row: dict[str, object] = {
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

    log.info(
        "Inserted %s rows into %s from inline SEED_ROWS",
        inserted,
        TABLE_NAME,
    )


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
