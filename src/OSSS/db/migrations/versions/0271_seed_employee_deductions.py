from __future__ import annotations

import logging
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0271"
down_revision = "0270"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "employee_deductions"


# Inline seed rows with realistic deduction values for a single payroll run/employee
SEED_ROWS = [
    {
        # Medical insurance premium (employee share)
        "id": "32515800-9f0a-50e7-9ea3-0a51a6c5ee82",
        "run_id": "0c29bab6-a225-55dc-9823-a14e870d86a3",
        "employee_id": "00000000-0000-0000-0000-000000000001",
        "deduction_code_id":"cba98ada-b903-56a3-afc1-574d9e45e19f",
        "amount": 250.00,
        "attributes": {
            "deduction_type": "medical_insurance",
            "coverage": "employee_plus_family",
            "pre_tax": True,
        },
        "created_at": datetime(2024, 1, 1, 1, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 1, 0, tzinfo=timezone.utc),
    },
    {
        # Dental insurance premium
        "id": "e10ca448-0371-5e48-b95d-0b1dc5d84219",
        "run_id": "0c29bab6-a225-55dc-9823-a14e870d86a3",
        "employee_id":  "00000000-0000-0000-0000-000000000001",
        "deduction_code_id": "cba98ada-b903-56a3-afc1-574d9e45e19f",
        "amount": 35.00,
        "attributes": {
            "deduction_type": "dental_insurance",
            "coverage": "employee_plus_spouse",
            "pre_tax": True,
        },
        "created_at": datetime(2024, 1, 1, 2, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 2, 0, tzinfo=timezone.utc),
    },
    {
        # Vision insurance premium
        "id": "92317c88-00a2-5fa7-bdcf-5117d60bb611",
        "run_id": "0c29bab6-a225-55dc-9823-a14e870d86a3",
        "employee_id":  "00000000-0000-0000-0000-000000000001",
        "deduction_code_id": "cba98ada-b903-56a3-afc1-574d9e45e19f",
        "amount": 18.50,
        "attributes": {
            "deduction_type": "vision_insurance",
            "coverage": "employee_only",
            "pre_tax": True,
        },
        "created_at": datetime(2024, 1, 1, 3, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 3, 0, tzinfo=timezone.utc),
    },
    {
        # 403(b) retirement contribution
        "id": "5b927bc3-e9fb-563c-a61b-e91136e0db66",
        "run_id": "0c29bab6-a225-55dc-9823-a14e870d86a3",
        "employee_id":  "00000000-0000-0000-0000-000000000001",
        "deduction_code_id": "cba98ada-b903-56a3-afc1-574d9e45e19f",
        "amount": 175.00,
        "attributes": {
            "deduction_type": "retirement_403b",
            "pre_tax": True,
            "percentage_of_gross": 0.06,
        },
        "created_at": datetime(2024, 1, 1, 4, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 4, 0, tzinfo=timezone.utc),
    },
    {
        # Union dues (post-tax)
        "id": "3b39b36f-8eed-5c62-84bd-d9bacaeeb125",
        "run_id": "0c29bab6-a225-55dc-9823-a14e870d86a3",
        "employee_id":  "00000000-0000-0000-0000-000000000001",
        "deduction_code_id": "cba98ada-b903-56a3-afc1-574d9e45e19f",
        "amount": 25.00,
        "attributes": {
            "deduction_type": "union_dues",
            "pre_tax": False,
        },
        "created_at": datetime(2024, 1, 1, 5, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 5, 0, tzinfo=timezone.utc),
    },
]


def upgrade() -> None:
    """Seed employee_deductions with inline rows.

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
