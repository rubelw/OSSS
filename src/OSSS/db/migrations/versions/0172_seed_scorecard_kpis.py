from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0172"
down_revision = "0171"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "scorecard_kpis"

# Inline seed rows for scorecard_kpis
# Columns: id, scorecard_id, kpi_id, display_order
SEED_ROWS = [
    {
        "id": "47f2ce42-bd7b-5958-9afc-9c99cd76ed83",
        "scorecard_id": "3572579a-8bff-597f-a766-59bc9bb43d93",
        "kpi_id": "3f2096a2-71ff-55af-8922-524b675b6cab",
        "display_order": 1,
    },
    {
        "id": "46611798-7626-52a8-9e4a-3d4e568315b3",
        "scorecard_id": "3572579a-8bff-597f-a766-59bc9bb43d93",
        "kpi_id": "3f2096a2-71ff-55af-8922-524b675b6cab",
        "display_order": 2,
    },
    {
        "id": "23d54c15-26ea-5128-a525-0644fe2e307b",
        "scorecard_id": "3572579a-8bff-597f-a766-59bc9bb43d93",
        "kpi_id": "3f2096a2-71ff-55af-8922-524b675b6cab",
        "display_order": 3,
    },
    {
        "id": "a716f689-af9b-52eb-9da2-e476384ed85d",
        "scorecard_id": "3572579a-8bff-597f-a766-59bc9bb43d93",
        "kpi_id": "3f2096a2-71ff-55af-8922-524b675b6cab",
        "display_order": 4,
    },
    {
        "id": "1c6121c4-54dd-520a-b564-fa7f4afaf739",
        "scorecard_id": "3572579a-8bff-597f-a766-59bc9bb43d93",
        "kpi_id": "3f2096a2-71ff-55af-8922-524b675b6cab",
        "display_order": 5,
    },
]


def upgrade() -> None:
    """Load seed data for scorecard_kpis from inline SEED_ROWS.

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
