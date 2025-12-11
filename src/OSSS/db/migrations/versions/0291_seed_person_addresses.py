from __future__ import annotations

import csv  # kept for consistency with other migrations, though unused for seeding
import logging
import os
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0291"
down_revision = "0289"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "person_addresses"
CSV_FILE = os.path.join(os.path.dirname(__file__), "csv", f"{TABLE_NAME}.csv")

# Inline seed data (realistic)
# Columns: id, person_id, address_id, is_primary, created_at, updated_at
SEED_ROWS = [
    {
        # Current primary home address for this person
        "id": "c6fb4861-5b5a-5a0b-839b-1ec6959c0ca4",
        "person_id": "a09b6c88-3418-40b5-9f14-77800af409f7",
        "address_id": "040fe6e6-291a-48ea-b609-42435a3e850e",
        "is_primary": True,
        "created_at": datetime(2024, 1, 1, 1, 0, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 1, 0, 0, tzinfo=timezone.utc),
    },
    {
        # Secondary mailing address (e.g., PO Box)
        "id": "663401d7-3dde-58b9-a911-e877cf445b30",
        "person_id": "a09b6c88-3418-40b5-9f14-77800af409f7",
        "address_id": "040fe6e6-291a-48ea-b609-42435a3e850e",
        "is_primary": False,
        "created_at": datetime(2024, 1, 1, 2, 0, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 2, 0, 0, tzinfo=timezone.utc),
    },
    {
        # Historical previous address, kept for records
        "id": "2ea46a1c-58b4-5c68-a578-71558b4510a1",
        "person_id": "a09b6c88-3418-40b5-9f14-77800af409f7",
        "address_id": "040fe6e6-291a-48ea-b609-42435a3e850e",
        "is_primary": False,
        "created_at": datetime(2024, 1, 1, 3, 0, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 3, 0, 0, tzinfo=timezone.utc),
    },
    {
        # Emergency contact address associated with this person
        "id": "6593951e-a19a-5b40-9d98-539605109c03",
        "person_id": "a09b6c88-3418-40b5-9f14-77800af409f7",
        "address_id": "040fe6e6-291a-48ea-b609-42435a3e850e",
        "is_primary": False,
        "created_at": datetime(2024, 1, 1, 4, 0, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 4, 0, 0, tzinfo=timezone.utc),
    },
    {
        # Additional non-primary address (e.g., summer residence)
        "id": "2342bb3b-7f80-556e-badb-4d64ca03582d",
        "person_id": "a09b6c88-3418-40b5-9f14-77800af409f7",
        "address_id": "040fe6e6-291a-48ea-b609-42435a3e850e",
        "is_primary": False,
        "created_at": datetime(2024, 1, 1, 5, 0, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 5, 0, 0, tzinfo=timezone.utc),
    },
]


def _coerce_value(col: sa.Column, raw):
    """For inline seeds we already provide appropriately-typed values."""
    return raw


def upgrade() -> None:
    """Seed person_addresses with realistic example rows."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(TABLE_NAME):
        log.warning("Table %s does not exist; skipping seed", TABLE_NAME)
        return

    metadata = sa.MetaData()
    table = sa.Table(TABLE_NAME, metadata, autoload_with=bind)

    inserted = 0
    for raw_row in SEED_ROWS:
        row = {}

        # Only keep keys that correspond to actual columns
        for col in table.columns:
            if col.name not in raw_row:
                continue
            row[col.name] = _coerce_value(col, raw_row[col.name])

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

    log.info("Inserted %s rows into %s", inserted, TABLE_NAME)


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
