from __future__ import annotations

import logging
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0281"
down_revision = "0280"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "message_recipients"

# Same message & person IDs as in the sample, but with realistic statuses
MESSAGE_ID = "33a2fb0b-263b-5b89-9402-01fa0fdd5bf2"
PERSON_ID = "a09b6c88-3418-40b5-9f14-77800af409f7"

# Inline seed rows representing the lifecycle of a single outbound message
SEED_ROWS = [
    {
        "id": "5737d617-4099-591e-9334-a13d66602e12",
        "message_id": MESSAGE_ID,
        "person_id": PERSON_ID,
        "delivery_status": "queued",
        "delivered_at": None,
        "created_at": datetime(2024, 1, 1, 1, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 1, 0, tzinfo=timezone.utc),
    },
    {
        "id": "1d770c49-669d-5bd9-bc2a-a41982bcf375",
        "message_id": MESSAGE_ID,
        "person_id": PERSON_ID,
        "delivery_status": "sending",
        "delivered_at": None,
        "created_at": datetime(2024, 1, 1, 1, 1, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 1, 1, tzinfo=timezone.utc),
    },
    {
        "id": "44b58e93-4cf5-54e7-8ccb-6956aa8bdb2e",
        "message_id": MESSAGE_ID,
        "person_id": PERSON_ID,
        "delivery_status": "delivered",
        "delivered_at": datetime(2024, 1, 1, 1, 2, tzinfo=timezone.utc),
        "created_at": datetime(2024, 1, 1, 1, 2, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 1, 2, tzinfo=timezone.utc),
    },
    {
        "id": "e4330626-d68d-53c1-bc81-0c2f935c4ba0",
        "message_id": MESSAGE_ID,
        "person_id": PERSON_ID,
        "delivery_status": "opened",
        "delivered_at": datetime(2024, 1, 1, 1, 5, tzinfo=timezone.utc),
        "created_at": datetime(2024, 1, 1, 1, 5, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 1, 5, tzinfo=timezone.utc),
    },
    {
        "id": "8b2c6e4c-2f7e-5f3d-9f19-7122fd93af19",
        "message_id": MESSAGE_ID,
        "person_id": PERSON_ID,
        "delivery_status": "archived",
        "delivered_at": datetime(2024, 1, 1, 1, 5, tzinfo=timezone.utc),
        "created_at": datetime(2024, 1, 1, 1, 10, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 1, 10, tzinfo=timezone.utc),
    },
]


def upgrade() -> None:
    """Seed message_recipients with inline rows.

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
