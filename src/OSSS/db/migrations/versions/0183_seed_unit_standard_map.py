from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0183"
down_revision = "0182"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "unit_standard_map"

# Inline seed rows for unit_standard_map
# Columns: unit_id, standard_id
SEED_ROWS = [
    {
        "unit_id": "cc885492-4e2f-5a5c-89f1-bd06ef5dd38a",
        "standard_id": "1f6a8a3e-3c2d-4b11-9f10-5e2a0c9b7a01",
    },
    {
        "unit_id": "c865194f-416c-5639-ab31-0168d1aea2ce",
        "standard_id": "1f6a8a3e-3c2d-4b11-9f10-5e2a0c9b7a01",
    },
    {
        "unit_id": "2107beaa-0569-58fe-8822-72d051dbfa08",
        "standard_id": "1f6a8a3e-3c2d-4b11-9f10-5e2a0c9b7a01",
    },
    {
        "unit_id": "e2f5f0df-128c-5360-949d-945cdf07a9bf",
        "standard_id": "1f6a8a3e-3c2d-4b11-9f10-5e2a0c9b7a01",
    },
    {
        "unit_id": "30c7a47c-7004-547e-8de4-3379795b0e06",
        "standard_id": "1f6a8a3e-3c2d-4b11-9f10-5e2a0c9b7a01",
    },
]


def upgrade() -> None:
    """Load seed data for unit_standard_map from inline SEED_ROWS.

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
        row: dict[str, object] = {
            col.name: raw_row[col.name]
            for col in table.columns
            if col.name in raw_row
        }

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

    log.info(
        "Inserted %s rows into %s from inline SEED_ROWS",
        inserted,
        TABLE_NAME,
    )


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
