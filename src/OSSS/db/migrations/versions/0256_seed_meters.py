from __future__ import annotations

import logging
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0256"
down_revision = "0255"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "meters"

ASSET_ID = "6c7a568b-721c-523d-b5c2-ce3fd6029630"
BUILDING_ID = "2fcc53b4-7367-5852-9afb-ffdecafad618"

# Inline seed rows with more realistic data
SEED_ROWS = [
    {
        "id": "1e270861-f8d9-5697-879d-ca19ea195726",
        "asset_id": ASSET_ID,
        "building_id": BUILDING_ID,
        "name": "Main electric meter - building total",
        "meter_type": "electric",
        "uom": "kWh",
        "last_read_value": 15432.7,
        "last_read_at": datetime(2024, 1, 1, 1, 0, tzinfo=timezone.utc),
        "attributes": {
            "phase": "3-phase",
            "voltage": "480V",
            "location": "MECH-01",
        },
        "created_at": datetime(2023, 12, 15, 8, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 1, 5, tzinfo=timezone.utc),
    },
    {
        "id": "c82964db-b774-500a-b193-f44f9b1650e2",
        "asset_id": ASSET_ID,
        "building_id": BUILDING_ID,
        "name": "Gas meter - boiler plant",
        "meter_type": "gas",
        "uom": "therm",
        "last_read_value": 892.3,
        "last_read_at": datetime(2024, 1, 1, 2, 0, tzinfo=timezone.utc),
        "attributes": {
            "pressure": "2 psi",
            "location": "BOILER-ROOM",
        },
        "created_at": datetime(2023, 12, 15, 8, 10, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 2, 5, tzinfo=timezone.utc),
    },
    {
        "id": "a5578c9b-821d-5f87-9960-0e10dfa25de0",
        "asset_id": ASSET_ID,
        "building_id": BUILDING_ID,
        "name": "Domestic water meter",
        "meter_type": "water",
        "uom": "gal",
        "last_read_value": 42175.0,
        "last_read_at": datetime(2024, 1, 1, 3, 0, tzinfo=timezone.utc),
        "attributes": {
            "location": "MAIN-ENTRY",
            "pipe_size": "2 in",
        },
        "created_at": datetime(2023, 12, 15, 8, 20, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 3, 5, tzinfo=timezone.utc),
    },
    {
        "id": "8c24274d-4865-5a30-8d9c-7183125c402c",
        "asset_id": ASSET_ID,
        "building_id": BUILDING_ID,
        "name": "Chilled water meter - cooling loop",
        "meter_type": "chilled_water",
        "uom": "ton-hrs",
        "last_read_value": 237.9,
        "last_read_at": datetime(2024, 1, 1, 4, 0, tzinfo=timezone.utc),
        "attributes": {
            "location": "CHILLER-PLANT",
            "loop": "CHW-01",
        },
        "created_at": datetime(2023, 12, 15, 8, 30, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 4, 5, tzinfo=timezone.utc),
    },
    {
        "id": "2681cfd9-7bb5-5966-8a0e-ae1efe7f94c6",
        "asset_id": ASSET_ID,
        "building_id": BUILDING_ID,
        "name": "Irrigation water meter",
        "meter_type": "irrigation_water",
        "uom": "gal",
        "last_read_value": 5120.0,
        "last_read_at": datetime(2024, 1, 1, 5, 0, tzinfo=timezone.utc),
        "attributes": {
            "location": "SERVICE-YARD",
            "zone_count": 6,
        },
        "created_at": datetime(2023, 12, 15, 8, 40, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 5, 5, tzinfo=timezone.utc),
    },
]


def upgrade() -> None:
    """Seed meters with inline rows.

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

    log.info("Inserted %s rows into %s", inserted, TABLE_NAME)


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
