from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0197"
down_revision = "0196"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "concession_items"

# Inline seed rows for concession_items
# Columns:
#   name, price_cents, inventory_quantity, stand_id,
#   active, school_id, id, created_at, updated_at
SEED_ROWS = [
    {
        "name": "Classic Butter Popcorn",
        "price_cents": 400,  # $4.00
        "inventory_quantity": 200,
        "stand_id": "2e75f487-2ef3-40bf-a9d2-489a24bb86f0",
        "active": True,
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "id": "cda1201e-f031-5175-b6b2-9d036be6d674",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
    },
    {
        "name": "Bottled Water (16 oz)",
        "price_cents": 200,  # $2.00
        "inventory_quantity": 500,
        "stand_id": "2e75f487-2ef3-40bf-a9d2-489a24bb86f0",
        "active": True,
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "id": "2d2fd20a-fba6-50e3-812a-f3d5ae2a8fc9",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
    },
    {
        "name": "All-Beef Hot Dog",
        "price_cents": 350,  # $3.50
        "inventory_quantity": 150,
        "stand_id": "2e75f487-2ef3-40bf-a9d2-489a24bb86f0",
        "active": True,
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "id": "7ff7a30e-3e08-55d8-a8af-ea92621cafc8",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
    },
    {
        "name": "Soft Pretzel with Salt",
        "price_cents": 300,  # $3.00
        "inventory_quantity": 120,
        "stand_id": "2e75f487-2ef3-40bf-a9d2-489a24bb86f0",
        "active": True,
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "id": "60933907-914d-5869-a36c-61315747bfdb",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
    },
    {
        "name": "Chocolate Candy Bar",
        "price_cents": 250,  # $2.50
        "inventory_quantity": 300,
        "stand_id": "2e75f487-2ef3-40bf-a9d2-489a24bb86f0",
        "active": False,  # temporarily inactive (sold out / not offered)
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "id": "3103982f-31e0-536b-8bb5-25d43ce8b3ed",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
    },
]


def upgrade() -> None:
    """Load seed data for concession_items from inline SEED_ROWS.

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
