from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0198"
down_revision = "0197"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "concession_sales"

# Inline seed rows for concession_sales
# Columns:
#   stand_id, event_id, buyer_name, buyer_email, buyer_phone,
#   buyer_address_line1, buyer_address_line2, buyer_city,
#   buyer_state, buyer_postal_code, school_id, id, created_at, updated_at
SEED_ROWS = [
    {
        "stand_id": "2e75f487-2ef3-40bf-a9d2-489a24bb86f0",
        "event_id": "13e28612-f86c-5753-8964-2ed13f37a8b4",
        "buyer_name": "Jordan Miller",
        "buyer_email": "jordan.miller@example.com",
        "buyer_phone": "555-201-0001",
        "buyer_address_line1": "123 Maple Street",
        "buyer_address_line2": "Apt 2A",
        "buyer_city": "Cedar Grove",
        "buyer_state": "IA",
        "buyer_postal_code": "50111",
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "id": "1e46fcec-e57a-58da-bffd-e5d19b233dc8",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
    },
    {
        "stand_id": "2e75f487-2ef3-40bf-a9d2-489a24bb86f0",
        "event_id": "13e28612-f86c-5753-8964-2ed13f37a8b4",
        "buyer_name": "Taylor Nguyen",
        "buyer_email": "taylor.nguyen@example.com",
        "buyer_phone": "555-201-0002",
        "buyer_address_line1": "456 Oak Avenue",
        "buyer_address_line2": "",
        "buyer_city": "Cedar Grove",
        "buyer_state": "IA",
        "buyer_postal_code": "50111",
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "id": "06cd1e96-88f8-54d6-aa3a-cc2de0874326",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
    },
    {
        "stand_id": "2e75f487-2ef3-40bf-a9d2-489a24bb86f0",
        "event_id": "13e28612-f86c-5753-8964-2ed13f37a8b4",
        "buyer_name": "Riley Johnson",
        "buyer_email": "riley.johnson@example.com",
        "buyer_phone": "555-201-0003",
        "buyer_address_line1": "789 Pine Lane",
        "buyer_address_line2": "",
        "buyer_city": "Cedar Grove",
        "buyer_state": "IA",
        "buyer_postal_code": "50111",
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "id": "7068ba36-3e34-5679-af63-cf612c10b644",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
    },
    {
        "stand_id": "2e75f487-2ef3-40bf-a9d2-489a24bb86f0",
        "event_id": "13e28612-f86c-5753-8964-2ed13f37a8b4",
        "buyer_name": "Alex Martinez",
        "buyer_email": "alex.martinez@example.com",
        "buyer_phone": "555-201-0004",
        "buyer_address_line1": "1010 Stadium Drive",
        "buyer_address_line2": "Concessions Booth 1",
        "buyer_city": "Cedar Grove",
        "buyer_state": "IA",
        "buyer_postal_code": "50111",
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "id": "77872e94-4291-508b-b25e-391f58e369c8",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
    },
    {
        "stand_id": "2e75f487-2ef3-40bf-a9d2-489a24bb86f0",
        "event_id": "13e28612-f86c-5753-8964-2ed13f37a8b4",
        "buyer_name": "Casey Patel",
        "buyer_email": "casey.patel@example.com",
        "buyer_phone": "555-201-0005",
        "buyer_address_line1": "222 Elm Street",
        "buyer_address_line2": "Unit B",
        "buyer_city": "Cedar Grove",
        "buyer_state": "IA",
        "buyer_postal_code": "50111",
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "id": "e3bc4a01-4f3b-506d-84e8-de66ddca781c",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
    },
]


def upgrade() -> None:
    """Load seed data for concession_sales from inline SEED_ROWS.

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
