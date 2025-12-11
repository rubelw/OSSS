from __future__ import annotations

import logging
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0285"
down_revision = "0284"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "bus_routes"

# Inline, realistic seed data
# Columns: name, school_id, created_at, updated_at, id
SEED_ROWS = [
    {
        "id": "dc004672-2936-552e-831b-4e2516959a9e",
        "name": "Route 1 – North Grimes Morning",
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "created_at": datetime(2024, 1, 1, 1, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 1, 0, tzinfo=timezone.utc),
    },
    {
        "id": "43ad4135-60f6-5ce3-87f6-c8e2b7665ca0",
        "name": "Route 2 – South Grimes Morning",
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "created_at": datetime(2024, 1, 1, 2, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 2, 0, tzinfo=timezone.utc),
    },
    {
        "id": "118dd7ba-380b-5b5c-b1a7-fabb3751f460",
        "name": "Route 3 – North Grimes Afternoon",
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "created_at": datetime(2024, 1, 1, 3, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 3, 0, tzinfo=timezone.utc),
    },
    {
        "id": "650b99fe-6d1e-5318-8264-bced90a9e075",
        "name": "Route 4 – South Grimes Afternoon",
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "created_at": datetime(2024, 1, 1, 4, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 4, 0, tzinfo=timezone.utc),
    },
    {
        "id": "1a92ebcc-be81-5f65-985b-a7a0fbaa0db0",
        "name": "Route 5 – Activities / Late Bus",
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "created_at": datetime(2024, 1, 1, 5, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 5, 0, tzinfo=timezone.utc),
    },
]


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion; for inline seeds we already use proper Python types."""
    return raw


def upgrade() -> None:
    """Seed bus_routes with a few realistic transportation routes."""
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
