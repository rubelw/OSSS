from __future__ import annotations

import csv  # kept for consistency with other migrations, though unused for seeding
import logging
import os
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0292"
down_revision = "0291"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "person_contacts"
CSV_FILE = os.path.join(os.path.dirname(__file__), "csv", f"{TABLE_NAME}.csv")

# Inline, realistic seed data
# Columns: id, person_id, contact_id, label, is_primary, is_emergency, created_at, updated_at
SEED_ROWS = [
    {
        # Primary guardian mobile number, also used for emergencies
        "id": "127dd520-ae3b-571b-9ee3-f170a2373042",
        "person_id": "a09b6c88-3418-40b5-9f14-77800af409f7",
        "contact_id": "334d4a32-2324-4ebe-80e4-1f4166d9806d",
        "label": "Primary Mobile",
        "is_primary": True,
        "is_emergency": True,
        "created_at": datetime(2024, 1, 1, 1, 0, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 1, 0, 0, tzinfo=timezone.utc),
    },
    {
        # Secondary mobile (other guardian)
        "id": "2b8bdf3f-852a-5dd4-8109-de193481c2c2",
        "person_id": "a09b6c88-3418-40b5-9f14-77800af409f7",
        "contact_id": "334d4a32-2324-4ebe-80e4-1f4166d9806d",
        "label": "Secondary Mobile",
        "is_primary": False,
        "is_emergency": True,
        "created_at": datetime(2024, 1, 1, 2, 0, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 2, 0, 0, tzinfo=timezone.utc),
    },
    {
        # Work email address, not used for emergencies
        "id": "cdc480eb-ca53-59fd-92d8-458134c9d505",
        "person_id": "a09b6c88-3418-40b5-9f14-77800af409f7",
        "contact_id": "334d4a32-2324-4ebe-80e4-1f4166d9806d",
        "label": "Work Email",
        "is_primary": False,
        "is_emergency": False,
        "created_at": datetime(2024, 1, 1, 3, 0, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 3, 0, 0, tzinfo=timezone.utc),
    },
    {
        # Home phone line
        "id": "c2d0ba0a-5145-528a-8e55-e738bf04704d",
        "person_id": "a09b6c88-3418-40b5-9f14-77800af409f7",
        "contact_id": "334d4a32-2324-4ebe-80e4-1f4166d9806d",
        "label": "Home Phone",
        "is_primary": False,
        "is_emergency": False,
        "created_at": datetime(2024, 1, 1, 4, 0, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 4, 0, 0, tzinfo=timezone.utc),
    },
    {
        # Alternate emergency-only contact (e.g., grandparent)
        "id": "bb83ba51-9f14-5460-b12a-c6e866c0989c",
        "person_id": "a09b6c88-3418-40b5-9f14-77800af409f7",
        "contact_id": "334d4a32-2324-4ebe-80e4-1f4166d9806d",
        "label": "Emergency Only",
        "is_primary": False,
        "is_emergency": True,
        "created_at": datetime(2024, 1, 1, 5, 0, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 5, 0, 0, tzinfo=timezone.utc),
    },
]


def _coerce_value(col: sa.Column, raw):
    """Inline seeds are already typed correctly; just return the value."""
    return raw


def upgrade() -> None:
    """Seed person_contacts with realistic example rows."""
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
