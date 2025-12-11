from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0184"
down_revision = "0183"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "proposal_standard_map"

# Inline seed rows for proposal_standard_map
# Columns: proposal_id, standard_id
SEED_ROWS = [
    {
        "proposal_id": "96bc433b-c25c-5870-80e2-b50df1bf1d66",
        "standard_id": "1f6a8a3e-3c2d-4b11-9f10-5e2a0c9b7a01",
    },
    {
        "proposal_id": "2497392e-25f8-5784-b0c9-7e46ed242dfe",
        "standard_id": "1f6a8a3e-3c2d-4b11-9f10-5e2a0c9b7a01",
    },
    {
        "proposal_id": "8ce5f006-9e4c-5546-ae2e-36f36166df11",
        "standard_id": "1f6a8a3e-3c2d-4b11-9f10-5e2a0c9b7a01",
    },
    {
        "proposal_id": "3025fe80-92e4-534b-987b-af09a478d46b",
        "standard_id": "1f6a8a3e-3c2d-4b11-9f10-5e2a0c9b7a01",
    },
    {
        "proposal_id": "b55db8e9-a3c5-5bf3-8c82-91c5e4433a1d",
        "standard_id": "1f6a8a3e-3c2d-4b11-9f10-5e2a0c9b7a01",
    },
]


def upgrade() -> None:
    """Load seed data for proposal_standard_map from inline SEED_ROWS.

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
