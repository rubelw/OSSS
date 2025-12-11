from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0180"
down_revision = "0179"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "score_entries"

# Inline seed rows for score_entries
# Columns: team_id, points, period, created_at, updated_at, game_id, id
SEED_ROWS = [
    {
        "team_id": "ee268bc5-47ec-59b2-b5bb-00492928ca1f",
        "points": 12,  # end of first quarter
        "period": "Q1",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
        "game_id": "35b62837-a339-5111-aa05-37dfbcebd7e7",
        "id": "21b9817a-23cd-502c-b5ab-1ef66449fea8",
    },
    {
        "team_id": "ee268bc5-47ec-59b2-b5bb-00492928ca1f",
        "points": 26,  # end of second quarter (halftime)
        "period": "Q2",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
        "game_id": "35b62837-a339-5111-aa05-37dfbcebd7e7",
        "id": "7ba59ebf-f4d3-5b4f-8498-5cd466bc47f9",
    },
    {
        "team_id": "ee268bc5-47ec-59b2-b5bb-00492928ca1f",
        "points": 39,  # end of third quarter
        "period": "Q3",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
        "game_id": "35b62837-a339-5111-aa05-37dfbcebd7e7",
        "id": "d92b51df-0837-5acc-8018-f8b7ea306e7b",
    },
    {
        "team_id": "ee268bc5-47ec-59b2-b5bb-00492928ca1f",
        "points": 52,  # end of regulation
        "period": "Q4",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
        "game_id": "35b62837-a339-5111-aa05-37dfbcebd7e7",
        "id": "da8d7b80-f3a0-52b0-8c3f-9034eaeeff17",
    },
    {
        "team_id": "ee268bc5-47ec-59b2-b5bb-00492928ca1f",
        "points": 60,  # final score after overtime
        "period": "OT",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
        "game_id": "35b62837-a339-5111-aa05-37dfbcebd7e7",
        "id": "2eb9588a-19a1-5800-a3d1-a78fdeeeb057",
    },
]


def upgrade() -> None:
    """Load seed data for score_entries from inline SEED_ROWS.

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
