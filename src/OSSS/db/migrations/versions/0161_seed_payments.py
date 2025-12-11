from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0161"
down_revision = "0160"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "payments"

# Inline seed rows for payments
# Columns: invoice_id, paid_on, amount, method, created_at, updated_at, id
# Updated to use realistic payment method names.
SEED_ROWS = [
    {
        "invoice_id": "08f7d0c6-0672-58e1-8187-eb7c0c284152",
        "paid_on": "2024-01-02",
        "amount": 1,
        "method": "Cash – received at school office",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
        "id": "d717109f-e647-5eba-9520-2f64449acb04",
    },
    {
        "invoice_id": "08f7d0c6-0672-58e1-8187-eb7c0c284152",
        "paid_on": "2024-01-03",
        "amount": 2,
        "method": "Check – mailed by family",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
        "id": "a8905847-c43d-5cda-9597-69602a92c52a",
    },
    {
        "invoice_id": "08f7d0c6-0672-58e1-8187-eb7c0c284152",
        "paid_on": "2024-01-04",
        "amount": 3,
        "method": "Credit card – online portal",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
        "id": "2acf8ae3-5e0a-50d5-9ef4-f5328e978552",
    },
    {
        "invoice_id": "08f7d0c6-0672-58e1-8187-eb7c0c284152",
        "paid_on": "2024-01-05",
        "amount": 4,
        "method": "ACH bank draft",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
        "id": "f013b7d3-6766-5fbe-9567-ce1bb69deb31",
    },
    {
        "invoice_id": "08f7d0c6-0672-58e1-8187-eb7c0c284152",
        "paid_on": "2024-01-06",
        "amount": 5,
        "method": "Fee waiver / adjustment",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
        "id": "f395b2b3-b462-5ab5-b030-50820308ff85",
    },
]


def upgrade() -> None:
    """Load seed data for payments from inline SEED_ROWS.

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
