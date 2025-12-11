from __future__ import annotations

import logging
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0282"
down_revision = "0281"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "entity_tags"

# Reuse the same IDs from the sample, but with realistic entity_type values
TAG_ID_PRIORITY = "2bb58942-5512-4ab3-948d-4a7afc8961db"

SEED_ROWS = [
    {
        "id": "6d1a261f-0814-5801-9634-070ae5676448",
        "entity_type": "student",
        "entity_id": "cb809c2d-9765-5713-9b74-0df75fadbc07",
        "tag_id": TAG_ID_PRIORITY,
        "created_at": datetime(2024, 1, 1, 1, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 1, 0, tzinfo=timezone.utc),
    },
    {
        "id": "c3f98b12-9b9d-5c68-9183-7672aa1c8026",
        "entity_type": "student",
        "entity_id": "b838b510-2807-5739-8d6c-c620525da7f6",
        "tag_id": TAG_ID_PRIORITY,
        "created_at": datetime(2024, 1, 1, 2, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 2, 0, tzinfo=timezone.utc),
    },
    {
        "id": "5dff2740-2d7b-5cb6-9ac7-33300586b3ef",
        "entity_type": "staff",
        "entity_id": "c9304828-b481-51ab-81ab-6fec5eb1228f",
        "tag_id": TAG_ID_PRIORITY,
        "created_at": datetime(2024, 1, 1, 3, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 3, 0, tzinfo=timezone.utc),
    },
    {
        "id": "37d8270f-cd8d-5b3c-b5d4-908b48f9ecb2",
        "entity_type": "building",
        "entity_id": "db43d1ce-a256-5517-b6dd-99998bba8e2f",
        "tag_id": TAG_ID_PRIORITY,
        "created_at": datetime(2024, 1, 1, 4, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 4, 0, tzinfo=timezone.utc),
    },
    {
        "id": "297849f1-4fee-5dbc-b53d-55ae6b0662be",
        "entity_type": "vendor",
        "entity_id": "64c62e0a-9d36-540d-95cd-5ad3f4450fbe",
        "tag_id": TAG_ID_PRIORITY,
        "created_at": datetime(2024, 1, 1, 5, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 5, 0, tzinfo=timezone.utc),
    },
]


def upgrade() -> None:
    """Seed entity_tags with a few realistic tagged entities.

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
