from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0154"
down_revision = "0153"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "incident_participants"

# Inline seed rows for incident_participants
# Columns: incident_id, person_id, role, id, created_at, updated_at
# Updated to use realistic participant role names.
SEED_ROWS = [
    {
        "incident_id": "9868063c-5b19-5bb6-aed1-927b1bc56093",
        "person_id": "a09b6c88-3418-40b5-9f14-77800af409f7",
        "role": "Student involved",
        "id": "7333748d-b32c-5724-ab8f-c769e06693d5",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
    },
    {
        "incident_id": "9868063c-5b19-5bb6-aed1-927b1bc56093",
        "person_id": "a09b6c88-3418-40b5-9f14-77800af409f7",
        "role": "Reporting staff member",
        "id": "09ca1e4d-72ac-5b19-b68d-2b98e76869c6",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
    },
    {
        "incident_id": "9868063c-5b19-5bb6-aed1-927b1bc56093",
        "person_id": "a09b6c88-3418-40b5-9f14-77800af409f7",
        "role": "Classroom teacher",
        "id": "2cc786af-ed09-5b67-90a7-89098fead47a",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
    },
    {
        "incident_id": "9868063c-5b19-5bb6-aed1-927b1bc56093",
        "person_id": "a09b6c88-3418-40b5-9f14-77800af409f7",
        "role": "Assistant principal",
        "id": "148fff5a-b5fa-536a-ae2c-14e3aa435943",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
    },
    {
        "incident_id": "9868063c-5b19-5bb6-aed1-927b1bc56093",
        "person_id": "a09b6c88-3418-40b5-9f14-77800af409f7",
        "role": "Counselor contacted",
        "id": "7dcd4fbf-af63-55fd-a051-3c2dd0d18eaa",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
    },
]


def upgrade() -> None:
    """Load seed data for incident_participants from inline SEED_ROWS.

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
        row: dict[str, object] = {}
        for col in table.columns:
            if col.name in raw_row:
                row[col.name] = raw_row[col.name]

        if not row:
            continue

        # Explicit nested transaction (SAVEPOINT)
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

    log.info("Inserted %s rows into %s from inline SEED_ROWS", inserted, TABLE_NAME)


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
