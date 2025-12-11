from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0156"
down_revision = "0155"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "library_holds"

# Inline seed rows for library_holds
# Columns: item_id, person_id, placed_on, expires_on, created_at, updated_at, id
SEED_ROWS = [
    {
        "item_id": "c0451751-a690-5352-8a41-d2e0a0c03ac4",
        "person_id": "a09b6c88-3418-40b5-9f14-77800af409f7",
        "placed_on": "2024-01-02",
        "expires_on": "2024-01-02",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
        "id": "c3356aa2-5283-554a-bce9-55baee62a34e",
    },
    {
        "item_id": "c0451751-a690-5352-8a41-d2e0a0c03ac4",
        "person_id": "a09b6c88-3418-40b5-9f14-77800af409f7",
        "placed_on": "2024-01-03",
        "expires_on": "2024-01-03",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
        "id": "5d474d3e-fb28-569b-9b4b-8a1f43bd4f20",
    },
    {
        "item_id": "c0451751-a690-5352-8a41-d2e0a0c03ac4",
        "person_id": "a09b6c88-3418-40b5-9f14-77800af409f7",
        "placed_on": "2024-01-04",
        "expires_on": "2024-01-04",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
        "id": "7ee8d87a-c7d7-5737-8262-71296a66096b",
    },
    {
        "item_id": "c0451751-a690-5352-8a41-d2e0a0c03ac4",
        "person_id": "a09b6c88-3418-40b5-9f14-77800af409f7",
        "placed_on": "2024-01-05",
        "expires_on": "2024-01-05",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
        "id": "abeca427-15c4-55a7-97eb-ff249d8836ef",
    },
    {
        "item_id": "c0451751-a690-5352-8a41-d2e0a0c03ac4",
        "person_id": "a09b6c88-3418-40b5-9f14-77800af409f7",
        "placed_on": "2024-01-06",
        "expires_on": "2024-01-06",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
        "id": "f7f55e3f-6179-5d3a-80af-3c8cb974eb86",
    },
]


def upgrade() -> None:
    """Load seed data for library_holds from inline SEED_ROWS.

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
