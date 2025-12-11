from __future__ import annotations

import logging
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0286"
down_revision = "0285"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "bus_stops"

# Inline, realistic seed data
# Columns: route_id, name, latitude, longitude, created_at, updated_at, id
SEED_ROWS = [
    {
        "id": "c6715e2f-3d54-5193-913a-112e1faadb14",
        "route_id": "dc004672-2936-552e-831b-4e2516959a9e",  # Route 1 – North Grimes Morning
        "name": "NW 1st St & N James St",
        "latitude": 41.6875,
        "longitude": -93.7902,
        "created_at": datetime(2024, 1, 1, 1, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 1, 0, tzinfo=timezone.utc),
    },
    {
        "id": "09e0fc0b-c57b-59aa-810b-ed6896bfa68d",
        "route_id": "dc004672-2936-552e-831b-4e2516959a9e",
        "name": "NW 6th St & NW Cherry Pkwy",
        "latitude": 41.6898,
        "longitude": -93.7881,
        "created_at": datetime(2024, 1, 1, 2, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 2, 0, tzinfo=timezone.utc),
    },
    {
        "id": "4fa35f36-ee34-524f-92fc-75c3f4cbd430",
        "route_id": "dc004672-2936-552e-831b-4e2516959a9e",
        "name": "NW 10th St & NW Brookside Dr",
        "latitude": 41.6921,
        "longitude": -93.7854,
        "created_at": datetime(2024, 1, 1, 3, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 3, 0, tzinfo=timezone.utc),
    },
    {
        "id": "9695029f-26d6-556a-b3e8-5bd0fbb01494",
        "route_id": "dc004672-2936-552e-831b-4e2516959a9e",
        "name": "NW 11th St & NW Trail Ridge Dr",
        "latitude": 41.6940,
        "longitude": -93.7829,
        "created_at": datetime(2024, 1, 1, 4, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 4, 0, tzinfo=timezone.utc),
    },
    {
        "id": "e3d17b99-32fd-50b3-be1c-87d3d00b2786",
        "route_id": "dc004672-2936-552e-831b-4e2516959a9e",
        "name": "DC-G Middle School Front Loop",
        "latitude": 41.6962,
        "longitude": -93.7801,
        "created_at": datetime(2024, 1, 1, 5, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 5, 0, tzinfo=timezone.utc),
    },
]


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion; for inline seeds we already use proper Python types."""
    return raw


def upgrade() -> None:
    """Seed bus_stops with a few realistic stops for Route 1."""
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

        # Only include keys that actually exist as columns
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
