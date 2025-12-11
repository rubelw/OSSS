from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0160"
down_revision = "0159"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "invoices"

# Inline seed rows for invoices
# Columns: student_id, issued_on, due_on, status, created_at, updated_at, id
# Updated to use realistic invoice status names.
SEED_ROWS = [
    {
        "student_id": "d4f53e78-1012-5322-a4f3-4bca2efc51be",
        "issued_on": "2024-01-02",
        "due_on": "2024-01-02",
        "status": "Draft – not yet sent",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
        "id": "08f7d0c6-0672-58e1-8187-eb7c0c284152",
    },
    {
        "student_id": "d4f53e78-1012-5322-a4f3-4bca2efc51be",
        "issued_on": "2024-01-03",
        "due_on": "2024-01-03",
        "status": "Issued – sent to family",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
        "id": "70b7b60a-a2cd-5a78-94cc-d33799f3d057",
    },
    {
        "student_id": "d4f53e78-1012-5322-a4f3-4bca2efc51be",
        "issued_on": "2024-01-04",
        "due_on": "2024-01-04",
        "status": "Partially paid",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
        "id": "504edf54-b448-51f9-b18b-8414a1b1303f",
    },
    {
        "student_id": "d4f53e78-1012-5322-a4f3-4bca2efc51be",
        "issued_on": "2024-01-05",
        "due_on": "2024-01-05",
        "status": "Paid in full",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
        "id": "3ee15823-f8e6-50f6-97cd-5d466e9bb1df",
    },
    {
        "student_id": "d4f53e78-1012-5322-a4f3-4bca2efc51be",
        "issued_on": "2024-01-06",
        "due_on": "2024-01-06",
        "status": "Voided / cancelled",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
        "id": "75bd7f09-6a15-5ede-879d-dc523927428c",
    },
]


def upgrade() -> None:
    """Load seed data for invoices from inline SEED_ROWS.

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

    log.info("Inserted %s rows into %s from inline SEED_ROWS", inserted, TABLE_NAME)


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
