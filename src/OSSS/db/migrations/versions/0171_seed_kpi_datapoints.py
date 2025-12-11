from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0171"
down_revision = "0170"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "kpi_datapoints"

# Inline seed rows for kpi_datapoints
# Columns: note, kpi_id, as_of, value, id, created_at, updated_at
# Updated with realistic KPI datapoint notes.
SEED_ROWS = [
    {
        "note": "Baseline value at start of winter term",
        "kpi_id": "3f2096a2-71ff-55af-8922-524b675b6cab",
        "as_of": "2024-01-02",
        "value": 1,
        "id": "9b0e40b7-171c-5450-ba9c-a8d445fa97a2",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
    },
    {
        "note": "Slight improvement after early intervention supports",
        "kpi_id": "3f2096a2-71ff-55af-8922-524b675b6cab",
        "as_of": "2024-01-03",
        "value": 2,
        "id": "d9ae071f-3a2f-5b9c-9650-2362f217180c",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
    },
    {
        "note": "Mid-week check: trend continuing in positive direction",
        "kpi_id": "3f2096a2-71ff-55af-8922-524b675b6cab",
        "as_of": "2024-01-04",
        "value": 3,
        "id": "dd481c41-224c-5709-9047-56240dd1d088",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
    },
    {
        "note": "Additional strategies implemented; growth accelerating",
        "kpi_id": "3f2096a2-71ff-55af-8922-524b675b6cab",
        "as_of": "2024-01-05",
        "value": 4,
        "id": "fc8cea10-1f7c-57f1-a4fe-ba8027a199d2",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
    },
    {
        "note": "End-of-week data point – target for this period reached",
        "kpi_id": "3f2096a2-71ff-55af-8922-524b675b6cab",
        "as_of": "2024-01-06",
        "value": 5,
        "id": "81e88645-4ac9-5f5f-b959-20bb350ce53c",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
    },
]


def upgrade() -> None:
    """Load seed data for kpi_datapoints from inline SEED_ROWS.

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

    log.info(
        "Inserted %s rows into %s from inline SEED_ROWS",
        inserted,
        TABLE_NAME,
    )


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
