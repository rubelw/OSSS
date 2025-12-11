from __future__ import annotations

import logging
from datetime import date, datetime, timezone

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0266"
down_revision = "0264"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "journal_entries"

BATCH_ID = "fd7d8eaf-38f2-476d-af02-ea9776c6b082"

# Inline seed rows with realistic journal entry data
SEED_ROWS = [
    {
        "id": "e089fc6c-3f15-5a00-b6e7-4e07259293be",
        "fiscal_period_id": "e03a4e59-941e-4c97-9d53-c4b72c77392e",
        "je_no": "JE-2024-0001",
        "journal_date": date(2024, 1, 2),
        "description": "Accrual for December utilities",
        "status": "posted",
        "total_debits": 1250.00,
        "total_credits": 1250.00,
        "batch_id": "fd7d8eaf-38f2-476d-af02-ea9776c6b082",
        "created_at": datetime(2024, 1, 1, 1, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 1, 0, tzinfo=timezone.utc),
    },

]


def upgrade() -> None:
    """Seed journal_entries with inline rows.

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
