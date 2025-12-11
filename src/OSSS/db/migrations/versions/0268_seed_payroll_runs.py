from __future__ import annotations

import logging
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0268"
down_revision = "0267"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "payroll_runs"


SEED_ROWS = [

    {
        # Calculated run (totals computed, not yet approved)
        "id": "0c29bab6-a225-55dc-9823-a14e870d86a3",
        "pay_period_id": "729d8618-d1e8-4fec-88cb-788c59c2a526",
        "run_no": 2,
        "status": "calculated",
        "created_by_user_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "posted_entry_id": None,
        "created_at": datetime(2024, 1, 15, 12, 5, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 15, 12, 5, tzinfo=timezone.utc),
    },

]


def upgrade() -> None:
    """Seed payroll_runs with inline rows.

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
