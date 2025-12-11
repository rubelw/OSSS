from __future__ import annotations

import logging
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0276"
down_revision = "0275"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "external_ids"

# Inline seed rows with realistic values
SEED_ROWS = [
    {
        # State SIS identifier for a student
        "id": "5d0f0254-cae2-468d-93e0-373be9896726",
        "entity_type": "student",
        "entity_id": "1d019938-4235-5769-88f4-66afdbc56087",
        "system": "state_sis",
        "external_id": "STATESIS-1001",
        "created_at": datetime(2024, 1, 1, 1, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 1, 0, tzinfo=timezone.utc),
    },
    {
        # Transportation routing system identifier for a student
        "id": "1ae5e82a-1361-4cc3-a087-bbc14d901d39",
        "entity_type": "student",
        "entity_id": "57bd2662-2c1c-5650-8556-01598ce49aa6",
        "system": "transportation_routing",
        "external_id": "TRANSPORTATION-1002",
        "created_at": datetime(2024, 1, 1, 2, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 2, 0, tzinfo=timezone.utc),
    },
    {
        # Cafeteria/point-of-sale system identifier for a staff member
        "id": "ee0cf66f-9ce4-4320-95ae-53f43216fec2",
        "entity_type": "staff",
        "entity_id": "3669f32a-54e8-5ce3-aa69-9f0b2bcc6dcf",
        "system": "cafeteria_pos",
        "external_id": "CAFETERIA-1003",
        "created_at": datetime(2024, 1, 1, 3, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 3, 0, tzinfo=timezone.utc),
    },
    {
        # Library management system identifier for a staff member
        "id": "efb8c997-0977-490c-94a6-291e435e0583",
        "entity_type": "staff",
        "entity_id": "19e2c204-cf1f-592d-bb9b-0d22155445e4",
        "system": "library_system",
        "external_id": "LIBRARY-1004",
        "created_at": datetime(2024, 1, 1, 4, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 4, 0, tzinfo=timezone.utc),
    },
    {
        # HR/payroll system identifier for a staff member
        "id": "878448aa-4e85-4c1a-8138-65b54b6ff380",
        "entity_type": "staff",
        "entity_id": "ec1fc4d8-bc9e-5676-bc1a-dea7b6b048cc",
        "system": "hr_payroll",
        "external_id": "HR-1005",
        "created_at": datetime(2024, 1, 1, 5, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 5, 0, tzinfo=timezone.utc),
    },
]


def upgrade() -> None:
    """Seed external_ids with inline rows.

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
