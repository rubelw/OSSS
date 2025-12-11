from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0165"
down_revision = "0164"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "emergency_contacts"

# Inline seed rows for emergency_contacts
# Columns: person_id, contact_name, relationship, phone, created_at, updated_at, id
SEED_ROWS = [
    {
        "person_id": "a09b6c88-3418-40b5-9f14-77800af409f7",
        "contact_name": "Jordan Smith",
        "relationship": "Mother",
        "phone": "555-555-0101",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
        "id": "2971f8c9-8876-5cc2-a641-0919d89c779f",
    },
    {
        "person_id": "a09b6c88-3418-40b5-9f14-77800af409f7",
        "contact_name": "Alex Smith",
        "relationship": "Father",
        "phone": "555-555-0102",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
        "id": "4afcccf7-ac40-5a6a-af01-4879c4967ac2",
    },
    {
        "person_id": "a09b6c88-3418-40b5-9f14-77800af409f7",
        "contact_name": "Taylor Johnson",
        "relationship": "Grandparent",
        "phone": "555-555-0103",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
        "id": "848ff81d-fdc2-5ebf-830d-9f79aa465bd6",
    },
    {
        "person_id": "a09b6c88-3418-40b5-9f14-77800af409f7",
        "contact_name": "Morgan Lee",
        "relationship": "Family friend",
        "phone": "555-555-0104",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
        "id": "6014ba89-af50-5d1a-853c-350c244c6abb",
    },
    {
        "person_id": "a09b6c88-3418-40b5-9f14-77800af409f7",
        "contact_name": "Casey Rivera",
        "relationship": "Neighbor",
        "phone": "555-555-0105",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
        "id": "6ca65389-117f-5e54-84ef-7ecd270b1572",
    },
]


def upgrade() -> None:
    """Load seed data for emergency_contacts from inline SEED_ROWS.

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
