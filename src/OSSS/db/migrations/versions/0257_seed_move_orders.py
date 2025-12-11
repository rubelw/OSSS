from __future__ import annotations

import logging
from datetime import date, datetime, timezone

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0257"
down_revision = "0256"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "move_orders"



# Inline seed rows with more realistic data
SEED_ROWS = [
    {
        "id": "3ec891c8-9303-53ba-91b2-9e847476e6c3",
        "project_id": "54bb3dda-4385-54bb-8939-0528dc95c1e2",
        "person_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "asset_id": "",
        "from_space_id": "8b3aa9d0-8d1e-5d94-8c02-9eb3a38e7e88",
        "to_space_id": "8b3aa9d0-8d1e-5d94-8c02-9eb3a38e7e89",
        "move_date": date(2024, 1, 8),
        "status": "requested",
        "attributes": {
            "reason": "Reconfigure workstation layout",
            "priority": "normal",
            "notes": "Move desk and filing cabinet within same room.",
        },
        "created_at": datetime(2024, 1, 1, 1, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 1, 0, tzinfo=timezone.utc),
    },

]


def upgrade() -> None:
    """Seed move_orders with inline rows.

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
