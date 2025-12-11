from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0170"
down_revision = "0169"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "evaluation_files"

# Inline seed rows for evaluation_files
# Columns: id, assignment_id, file_id
SEED_ROWS = [
    {
        "id": "ed14ddea-edb5-56ed-a9c6-dd6dfd30f563",
        "assignment_id": "a5d5a408-430c-57f7-941a-9bd0d8ed9049",
        "file_id": "39ca63db-2221-5408-ad28-c6dfaac3056d",
    },
    {
        "id": "a624f43d-53dd-5d2b-8abf-a3f2b00edd28",
        "assignment_id": "a5d5a408-430c-57f7-941a-9bd0d8ed9049",
        "file_id": "39ca63db-2221-5408-ad28-c6dfaac3056d",
    },
    {
        "id": "e9b21621-fd10-58d6-ac1c-950bbe47a25a",
        "assignment_id": "a5d5a408-430c-57f7-941a-9bd0d8ed9049",
        "file_id": "39ca63db-2221-5408-ad28-c6dfaac3056d",
    },
    {
        "id": "6026436b-32a6-5f5f-9c25-439445bd6209",
        "assignment_id": "a5d5a408-430c-57f7-941a-9bd0d8ed9049",
        "file_id": "39ca63db-2221-5408-ad28-c6dfaac3056d",
    },
    {
        "id": "81205cc8-ec12-5535-8dff-1ac03c0f7109",
        "assignment_id": "a5d5a408-430c-57f7-941a-9bd0d8ed9049",
        "file_id": "39ca63db-2221-5408-ad28-c6dfaac3056d",
    },
]


def upgrade() -> None:
    """Load seed data for evaluation_files from inline SEED_ROWS.

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
