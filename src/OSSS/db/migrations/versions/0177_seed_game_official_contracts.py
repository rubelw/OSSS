from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0177"
down_revision = "0176"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "game_official_contracts"

# Inline seed rows for game_official_contracts
# Columns: game_id, official_id, fee_cents, created_at, updated_at, id
SEED_ROWS = [
    {
        "game_id": "35b62837-a339-5111-aa05-37dfbcebd7e7",
        "official_id": "88456d31-3427-4443-8f46-7efd30e8848e",
        "fee_cents": 8500,  # $85.00 standard regular-season fee
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
        "id": "4a712a31-ad8d-52a9-be05-37488d8b0c2a",
    },
    {
        "game_id": "35b62837-a339-5111-aa05-37dfbcebd7e7",
        "official_id": "88456d31-3427-4443-8f46-7efd30e8848e",
        "fee_cents": 9000,  # $90.00 weekend rate
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
        "id": "04275fa2-df99-5471-bf41-e9fcdefdb1ae",
    },
    {
        "game_id": "35b62837-a339-5111-aa05-37dfbcebd7e7",
        "official_id": "88456d31-3427-4443-8f46-7efd30e8848e",
        "fee_cents": 9500,  # $95.00 rivalry/featured game
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
        "id": "911890db-ecbe-5200-8648-a63a89b217a5",
    },
    {
        "game_id": "35b62837-a339-5111-aa05-37dfbcebd7e7",
        "official_id": "88456d31-3427-4443-8f46-7efd30e8848e",
        "fee_cents": 10000,  # $100.00 tournament game
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
        "id": "881e5381-0164-5906-88ff-909086bd1d0a",
    },
    {
        "game_id": "35b62837-a339-5111-aa05-37dfbcebd7e7",
        "official_id": "88456d31-3427-4443-8f46-7efd30e8848e",
        "fee_cents": 12500,  # $125.00 playoff / championship rate
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
        "id": "907651b5-d08d-5656-b092-56586d9e0313",
    },
]


def upgrade() -> None:
    """Load seed data for game_official_contracts from inline SEED_ROWS.

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
