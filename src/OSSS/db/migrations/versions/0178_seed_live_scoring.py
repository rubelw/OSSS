from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0178"
down_revision = "0177"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "live_scoring"

# Inline seed rows for live_scoring
# Columns: game_id, score, status, created_at, updated_at, id
SEED_ROWS = [
    {
        "game_id": "35b62837-a339-5111-aa05-37dfbcebd7e7",
        "score": 8,  # early first-quarter score
        "status": "in_progress_q1",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
        "id": "190f9c91-ad74-5fd7-853e-c195994a6f0d",
    },
    {
        "game_id": "35b62837-a339-5111-aa05-37dfbcebd7e7",
        "score": 21,  # late first / early second quarter
        "status": "in_progress_q2",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
        "id": "c176ac71-dd8f-59b6-b38a-60bbbbc62110",
    },
    {
        "game_id": "35b62837-a339-5111-aa05-37dfbcebd7e7",
        "score": 34,  # halftime snapshot
        "status": "halftime",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
        "id": "c5748497-dc6a-5f56-b6f0-c63ba12ccab7",
    },
    {
        "game_id": "35b62837-a339-5111-aa05-37dfbcebd7e7",
        "score": 50,  # late third / early fourth quarter
        "status": "in_progress_q4",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
        "id": "489c41f9-9e6d-5966-b0bc-cbb1500fc027",
    },
    {
        "game_id": "35b62837-a339-5111-aa05-37dfbcebd7e7",
        "score": 62,  # final score snapshot
        "status": "final",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
        "id": "7765455f-a018-5543-a886-0c27fcad5cf0",
    },
]


def upgrade() -> None:
    """Load seed data for live_scoring from inline SEED_ROWS.

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
