from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0056"
down_revision = "0055"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "hr_employees"

# Inline seed data for hr_employees
SEED_ROWS = [
    {
        "person_id": "a09b6c88-3418-40b5-9f14-77800af409f7",
        "employee_no": "hr_employees_employee_no_1",
        "primary_school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "department_segment_id": "2b8a4b38-8e3e-41b2-b58e-9c0f1b4e0a01",
        "employment_type": "hr_employees_emp",
        "status": "hr_employees_sta",
        "hire_date": "2024-01-02",
        "termination_date": None,
        "attributes": {},
        "id": "00000000-0000-0000-0000-000000000001",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
    },
    {
        "person_id": "79d591b1-3536-4493-a88a-8dfd0b481ead",
        "employee_no": "hr_employees_employee_no_2",
        "primary_school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        # FIX: remove extra '3' so this is a valid UUID matching gl_segments
        "department_segment_id": "2b8a4b38-8e3e-41b2-b58e-9c0f1b4e0a01",
        "employment_type": "hr_employees_emp",
        "status": "hr_employees_sta",
        "hire_date": "2024-01-02",
        "termination_date": None,
        "attributes": {},
        "id": "00000000-0000-0000-0000-000000000002",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
    },
    {
        "person_id": "c473361d-aa2e-4ad0-bd0d-fcb73e3c780b",
        "employee_no": "hr_employees_employee_no_3",
        "primary_school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "department_segment_id": "2b8a4b38-8e3e-41b2-b58e-9c0f1b4e0a01",
        "employment_type": "hr_employees_emp",
        "status": "hr_employees_sta",
        "hire_date": "2024-01-02",
        "termination_date": None,
        "attributes": {},
        "id": "00000000-0000-0000-0000-000000000003",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
    },
    {
        "person_id": "4d7d56ba-8041-4154-b626-6672ca04e989",
        "employee_no": "hr_employees_employee_no_4",
        "primary_school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "department_segment_id": "2b8a4b38-8e3e-41b2-b58e-9c0f1b4e0a01",
        "employment_type": "hr_employees_emp",
        "status": "hr_employees_sta",
        "hire_date": "2024-01-02",
        "termination_date": None,
        "attributes": {},
        "id": "00000000-0000-0000-0000-000000000004",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
    },
    {
        "person_id": "2a0942e2-d035-4406-ba6b-fa61ba1f19d8",
        "employee_no": "hr_employees_employee_no_5",
        "primary_school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "department_segment_id": "2b8a4b38-8e3e-41b2-b58e-9c0f1b4e0a01",
        "employment_type": "hr_employees_emp",
        "status": "hr_employees_sta",
        "hire_date": "2024-01-02",
        "termination_date": None,
        "attributes": {},
        "id": "00000000-0000-0000-0000-000000000005",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
    },
    {
        "person_id": "4e4c3505-af2d-475b-9bf4-edc1aa4f6afb",
        "employee_no": "hr_employees_employee_no_6",
        "primary_school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "department_segment_id": "2b8a4b38-8e3e-41b2-b58e-9c0f1b4e0a01",
        "employment_type": "hr_employees_emp",
        "status": "hr_employees_sta",
        "hire_date": "2024-01-02",
        "termination_date": None,
        "attributes": {},
        "id": "00000000-0000-0000-0000-000000000006",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
    },
    {
        "person_id": "8ffa156a-43f4-418a-9819-774c58ea4217",
        "employee_no": "hr_employees_employee_no_7",
        "primary_school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "department_segment_id": "2b8a4b38-8e3e-41b2-b58e-9c0f1b4e0a01",
        "employment_type": "hr_employees_emp",
        "status": "hr_employees_sta",
        "hire_date": "2024-01-02",
        "termination_date": None,
        "attributes": {},
        "id": "00000000-0000-0000-0000-000000000007",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
    },
]


def upgrade() -> None:
    """Load seed data for hr_employees from inline constants.

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

    if not SEED_ROWS:
        log.info("No inline seed rows defined for %s", TABLE_NAME)
        return

    inserted = 0
    for raw_row in SEED_ROWS:
        row: dict[str, object] = {}

        for col in table.columns:
            if col.name not in raw_row:
                continue
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

    log.info("Inserted %s hr_employees rows from inline seed data", inserted)


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
