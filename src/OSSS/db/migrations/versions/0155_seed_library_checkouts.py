from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0155"
down_revision = "0154"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "library_checkouts"

# Inline seed rows for library_checkouts
# Columns: item_id, person_id, checked_out_on, due_on, returned_on,
#          created_at, updated_at, id
SEED_ROWS = [
    {
        "item_id": "c0451751-a690-5352-8a41-d2e0a0c03ac4",
        "person_id": "a09b6c88-3418-40b5-9f14-77800af409f7",
        "checked_out_on": "2024-01-02",
        "due_on": "2024-01-02",
        "returned_on": "2024-01-02",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
        "id": "7e588deb-cfe9-5062-9d19-d51e9a4afe4b",
    },
    {
        "item_id": "c0451751-a690-5352-8a41-d2e0a0c03ac4",
        "person_id": "a09b6c88-3418-40b5-9f14-77800af409f7",
        "checked_out_on": "2024-01-03",
        "due_on": "2024-01-03",
        "returned_on": "2024-01-03",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
        "id": "5ea34a79-c90a-51d4-8b44-d05831ca5ce8",
    },
    {
        "item_id": "c0451751-a690-5352-8a41-d2e0a0c03ac4",
        "person_id": "a09b6c88-3418-40b5-9f14-77800af409f7",
        "checked_out_on": "2024-01-04",
        "due_on": "2024-01-04",
        "returned_on": "2024-01-04",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
        "id": "18bdd8ea-11d8-59f6-a6bd-4aa1ed77894e",
    },
    {
        "item_id": "c0451751-a690-5352-8a41-d2e0a0c03ac4",
        "person_id": "a09b6c88-3418-40b5-9f14-77800af409f7",
        "checked_out_on": "2024-01-05",
        "due_on": "2024-01-05",
        "returned_on": "2024-01-05",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
        "id": "00dce32d-cf55-5a0c-8200-c7435f6ae162",
    },
    {
        "item_id": "c0451751-a690-5352-8a41-d2e0a0c03ac4",
        "person_id": "a09b6c88-3418-40b5-9f14-77800af409f7",
        "checked_out_on": "2024-01-06",
        "due_on": "2024-01-06",
        "returned_on": "2024-01-06",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
        "id": "22e26ce0-cd56-59b9-b0fd-17d48b59a6b6",
    },
]


def upgrade() -> None:
    """Load seed data for library_checkouts from inline SEED_ROWS.

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
