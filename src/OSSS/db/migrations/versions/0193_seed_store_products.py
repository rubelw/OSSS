from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0193"
down_revision = "0192"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "store_products"

# Realistic inline seed rows for store_products.
# Note: we map unit prices (in dollars) to price_cents and include inventory_qty.
SEED_ROWS = [
    {
        "id": "29e63715-b3a3-4139-a97d-cf40cb3400fc",
        "sku": "SKU-101",
        "name": "Adult Football Ticket",
        "price_cents": 800,  # $8.00
        "inventory_qty": 500,
        "metadata": {
            "category": "Ticket",
            "active": True,
        },
    },
    {
        "id": "027294cb-f2a2-4894-84b7-9052dbaa5a45",
        "sku": "SKU-102",
        "name": "Student Football Ticket",
        "price_cents": 1100,  # $11.00
        "inventory_qty": 400,
        "metadata": {
            "category": "Ticket",
            "active": True,
        },
    },
    {
        "id": "5e61468e-80b6-484e-bd6b-467a704ab60f",
        "sku": "SKU-103",
        "name": "School T-Shirt",
        "price_cents": 1400,  # $14.00
        "inventory_qty": 250,
        "metadata": {
            "category": "Merchandise",
            "active": True,
            "sizes": ["S", "M", "L", "XL"],
        },
    },
    {
        "id": "996cb719-c460-488d-b489-a4cdce963a9d",
        "sku": "SKU-104",
        "name": "Yearbook",
        "price_cents": 1700,  # $17.00
        "inventory_qty": 150,
        "metadata": {
            "category": "Merchandise",
            "active": True,
            "school_year": "2023-2024",
        },
    },
    {
        "id": "4e12f957-94c5-4a94-984a-2969816cc666",
        "sku": "SKU-105",
        "name": "Activity Pass",
        "price_cents": 2000,  # $20.00
        "inventory_qty": 300,
        "metadata": {
            "category": "Merchandise",
            "active": True,
            "valid_for": "all_home_events",
        },
    },
]


def upgrade() -> None:
    """Seed store_products with inline data."""

    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(TABLE_NAME):
        log.warning("Table %s does not exist; skipping seed", TABLE_NAME)
        return

    metadata = sa.MetaData()
    table = sa.Table(TABLE_NAME, metadata, autoload_with=bind)

    inserted = 0
    for raw_row in SEED_ROWS:
        # Only include keys that correspond to real DB columns
        row = {
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
