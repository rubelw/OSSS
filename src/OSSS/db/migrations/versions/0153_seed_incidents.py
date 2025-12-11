from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0153"
down_revision = "0152"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "incidents"

# Inline seed rows for incidents
# Columns: school_id, occurred_at, behavior_code, description, id, created_at, updated_at
# Updated to use more realistic incident descriptions.
SEED_ROWS = [
    {
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "occurred_at": "2024-01-01T01:00:00Z",
        "behavior_code": "MINOR",
        "description": "Student engaged in minor classroom disruption (talking out of turn).",
        "id": "9868063c-5b19-5bb6-aed1-927b1bc56093",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
    },
    {
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "occurred_at": "2024-01-01T02:00:00Z",
        "behavior_code": "MINOR",
        "description": "Student arrived tardy to class without a pass.",
        "id": "e2b68350-6478-5d10-b7b1-83125cb4d81f",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
    },
    {
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "occurred_at": "2024-01-01T03:00:00Z",
        "behavior_code": "MINOR",
        "description": "Student ran in the hallway and ignored posted expectations.",
        "id": "e0388504-1b71-5cbf-893f-c615cc37030a",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
    },
    {
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "occurred_at": "2024-01-01T04:00:00Z",
        "behavior_code": "MINOR",
        "description": "Student used personal device during instruction without permission.",
        "id": "4f88e51e-c184-5caa-b6f5-b0368ad5e63a",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
    },
    {
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "occurred_at": "2024-01-01T05:00:00Z",
        "behavior_code": "MINOR",
        "description": "Student repeatedly off-task and not following teacher directions.",
        "id": "86140c30-4535-5bbe-b52b-8ade798b696a",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
    },
]


def upgrade() -> None:
    """Load seed data for incidents from inline SEED_ROWS.

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
        row = {}
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
