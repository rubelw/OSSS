from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0179"
down_revision = "0178"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "manual_stats"

# Inline seed rows for manual_stats
# Columns: stat_type, value, created_at, updated_at, game_id, id
SEED_ROWS = [
    {
        "stat_type": "offensive_rebounds",
        "value": 3,
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
        "game_id": "35b62837-a339-5111-aa05-37dfbcebd7e7",
        "id": "ccb10761-0212-52c4-bffd-09fa705c10e3",
    },
    {
        "stat_type": "defensive_rebounds",
        "value": 8,
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
        "game_id": "35b62837-a339-5111-aa05-37dfbcebd7e7",
        "id": "e6c21c79-a9ed-5621-864c-557557d7b036",
    },
    {
        "stat_type": "assists",
        "value": 5,
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
        "game_id": "35b62837-a339-5111-aa05-37dfbcebd7e7",
        "id": "28fdee36-6734-54fa-9679-49191d2a3b5c",
    },
    {
        "stat_type": "turnovers",
        "value": 2,
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
        "game_id": "35b62837-a339-5111-aa05-37dfbcebd7e7",
        "id": "46962138-dbf0-5ce3-9518-8cc181b36783",
    },
    {
        "stat_type": "personal_fouls",
        "value": 4,
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
        "game_id": "35b62837-a339-5111-aa05-37dfbcebd7e7",
        "id": "e366b3ec-008f-54c0-860e-5cc9bebcebec",
    },
]


def upgrade() -> None:
    """Load seed data for manual_stats from inline SEED_ROWS.

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
