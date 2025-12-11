from __future__ import annotations

import logging
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0269"
down_revision = "0268"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "paychecks"

# Sample foreign key IDs (must exist in payroll_runs and hr_employees for full FK integrity)
RUN_ID_JAN_15 = "11111111-2222-3333-4444-555555555555"
EMPLOYEE_ID_1 = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
EMPLOYEE_ID_2 = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff"
EMPLOYEE_ID_3 = "cccccccc-dddd-eeee-ffff-000000000000"

SEED_ROWS = [
    {
        "id": "2b9b1b6a-9b85-4b5e-9d6a-0a0a6f8c9b01",
        "run_id": "0c29bab6-a225-55dc-9823-a14e870d86a3",
        "employee_id": "00000000-0000-0000-0000-000000000001",
        "check_no": "CHK-2024-0001",
        "gross_pay": 2850.00,
        "net_pay": 1950.75,
        "taxes": {
            "federal": 450.25,
            "state": 130.00,
            "fica": 176.46,
            "medicare": 41.54,
        },
        "attributes": {
            "pay_period_start": "2024-01-01",
            "pay_period_end": "2024-01-15",
            "pay_type": "salary",
            "delivery_method": "direct_deposit",
            "bank_last4": "4321",
        },
        "created_at": datetime(2024, 1, 15, 14, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 15, 14, 0, tzinfo=timezone.utc),
    },
]


def upgrade() -> None:
    """Seed paychecks with inline rows.

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
