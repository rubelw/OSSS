from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0157"
down_revision = "0156"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "library_fines"

# Inline seed rows for library_fines
# Columns: person_id, amount, reason, assessed_on, paid_on, created_at, updated_at, id
# Updated to use realistic fine reason descriptions.
SEED_ROWS = [
    {
        "person_id": "a09b6c88-3418-40b5-9f14-77800af409f7",
        "amount": 1,
        "reason": "Overdue fine – 1 day late return",
        "assessed_on": "2024-01-02",
        "paid_on": "2024-01-02",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
        "id": "a82e739c-d95d-58ca-b649-6a9be5081797",
    },
    {
        "person_id": "a09b6c88-3418-40b5-9f14-77800af409f7",
        "amount": 2,
        "reason": "Overdue fine – 2 days late return",
        "assessed_on": "2024-01-03",
        "paid_on": "2024-01-03",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
        "id": "31af7326-c117-5f7e-80d9-e30e1fa94540",
    },
    {
        "person_id": "a09b6c88-3418-40b5-9f14-77800af409f7",
        "amount": 3,
        "reason": "Overdue fine – 3 days late return",
        "assessed_on": "2024-01-04",
        "paid_on": "2024-01-04",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
        "id": "e72d7ddc-8dba-5a01-bef5-cccabb06101c",
    },
    {
        "person_id": "a09b6c88-3418-40b5-9f14-77800af409f7",
        "amount": 4,
        "reason": "Damaged book fee – minor damage",
        "assessed_on": "2024-01-05",
        "paid_on": "2024-01-05",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
        "id": "ef2edccd-a4bd-55c1-8e46-2c7cbc35c533",
    },
    {
        "person_id": "a09b6c88-3418-40b5-9f14-77800af409f7",
        "amount": 5,
        "reason": "Replacement fee – item declared lost",
        "assessed_on": "2024-01-06",
        "paid_on": "2024-01-06",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
        "id": "e222a93d-5a7f-5024-8282-9389f20aab57",
    },
]


def upgrade() -> None:
    """Load seed data for library_fines from inline SEED_ROWS.

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
