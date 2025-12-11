from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0192"
down_revision = "0191"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "tickets"

# Inline seed rows for tickets
# Columns:
# order_id, ticket_type_id, event_id, qr_code, status,
# issued_at, redeemed_at, id, created_at, updated_at
SEED_ROWS = [
    {
        # Ticket 1 – redeemed general admission ticket
        "order_id": "c4f8bc7f-a2ef-5587-b637-901a3096acec",
        "ticket_type_id": "4408eb5e-fcb7-5e86-885a-a08b5bf3015c",
        "event_id": "13e28612-f86c-5753-8964-2ed13f37a8b4",
        "qr_code": "EVT-20240105-GA-0001",
        "status": "redeemed",
        "issued_at": "2024-01-01T01:00:00Z",
        "redeemed_at": "2024-01-01T01:00:00Z",
        "id": "026ebaa1-aaed-56e7-9fdf-7fbf70a072d1",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
    },
    {
        # Ticket 2 – redeemed general admission ticket
        "order_id": "c4f8bc7f-a2ef-5587-b637-901a3096acec",
        "ticket_type_id": "4408eb5e-fcb7-5e86-885a-a08b5bf3015c",
        "event_id": "13e28612-f86c-5753-8964-2ed13f37a8b4",
        "qr_code": "EVT-20240105-GA-0002",
        "status": "redeemed",
        "issued_at": "2024-01-01T02:00:00Z",
        "redeemed_at": "2024-01-01T02:00:00Z",
        "id": "e761953e-658c-5244-8ea6-0214fdca5183",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
    },
    {
        # Ticket 3 – issued but not yet redeemed
        "order_id": "c4f8bc7f-a2ef-5587-b637-901a3096acec",
        "ticket_type_id": "4408eb5e-fcb7-5e86-885a-a08b5bf3015c",
        "event_id": "13e28612-f86c-5753-8964-2ed13f37a8b4",
        "qr_code": "EVT-20240105-GA-0003",
        "status": "issued",
        "issued_at": "2024-01-01T03:00:00Z",
        "redeemed_at": None,
        "id": "36275666-2120-5cfb-ac5b-eabcbec6fb69",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
    },
    {
        # Ticket 4 – voided ticket
        "order_id": "c4f8bc7f-a2ef-5587-b637-901a3096acec",
        "ticket_type_id": "4408eb5e-fcb7-5e86-885a-a08b5bf3015c",
        "event_id": "13e28612-f86c-5753-8964-2ed13f37a8b4",
        "qr_code": "EVT-20240105-GA-0004",
        "status": "void",
        "issued_at": "2024-01-01T04:00:00Z",
        "redeemed_at": None,
        "id": "8dbf0cbd-02d6-59ba-9bd1-560f07ac719a",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
    },
    {
        # Ticket 5 – redeemed general admission ticket
        "order_id": "c4f8bc7f-a2ef-5587-b637-901a3096acec",
        "ticket_type_id": "4408eb5e-fcb7-5e86-885a-a08b5bf3015c",
        "event_id": "13e28612-f86c-5753-8964-2ed13f37a8b4",
        "qr_code": "EVT-20240105-GA-0005",
        "status": "redeemed",
        "issued_at": "2024-01-01T05:00:00Z",
        "redeemed_at": "2024-01-01T05:00:00Z",
        "id": "09d24686-b617-5d0c-8e64-2a5bd400dd81",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
    },
]


def upgrade() -> None:
    """Load seed data for tickets from inline SEED_ROWS.

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
