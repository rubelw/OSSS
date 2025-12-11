from __future__ import annotations

import logging
from datetime import datetime, date, timezone

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0274"
down_revision = "0273"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "data_sharing_agreements"

SEED_ROWS = [
    {
        "id": "5f8c39ff-e587-4d03-abf9-52b9b20f0c24",
        "vendor": "Grimes City Public Library",
        "scope": "Limited directory information for student library card program.",
        "start_date": date(2024, 8, 2),
        "end_date": date(2025, 8, 2),
        "notes": "Agreement with City Library for limited sharing of student name, grade, and school for library card eligibility.",
        "created_at": datetime(2024, 1, 1, 1, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 1, 0, tzinfo=timezone.utc),
    },
    {
        "id": "c7ae8f49-0af1-4745-9ef0-9235b17cf07a",
        "vendor": "Central Iowa Education Service Agency",
        "scope": "Assessment scores and enrollment data for regional support services.",
        "start_date": date(2024, 8, 3),
        "end_date": date(2025, 8, 3),
        "notes": "Agreement with Educational Service Agency for limited data sharing to support regional professional development and reporting.",
        "created_at": datetime(2024, 1, 1, 2, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 2, 0, tzinfo=timezone.utc),
    },
    {
        "id": "7568f4e0-c792-431a-81db-be966b3be22d",
        "vendor": "Statewide Assessment Vendor",
        "scope": "Student identifiers and assessment results for state-required testing.",
        "start_date": date(2024, 8, 4),
        "end_date": date(2025, 8, 4),
        "notes": "Agreement with assessment vendor for secure transfer of student rosters and test results for state accountability.",
        "created_at": datetime(2024, 1, 1, 3, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 3, 0, tzinfo=timezone.utc),
    },
    {
        "id": "03b4a77e-3af0-451c-89be-f3a6974b028e",
        "vendor": "Student Transportation Services, LLC",
        "scope": "Student address and route assignments for bus routing.",
        "start_date": date(2024, 8, 5),
        "end_date": date(2025, 8, 5),
        "notes": "Agreement with transportation contractor for limited sharing of student address, grade, and schedule needed for route planning.",
        "created_at": datetime(2024, 1, 1, 4, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 4, 0, tzinfo=timezone.utc),
    },
    {
        "id": "b21d5a3d-a506-4b38-bdfe-79e2d5791c96",
        "vendor": "After-School Enrichment Partners, Inc.",
        "scope": "Student contact and enrollment details for after-school programs.",
        "start_date": date(2024, 8, 6),
        "end_date": date(2025, 8, 6),
        "notes": "Agreement with after-school nonprofit for limited sharing of student and guardian contact info for program rosters and communication.",
        "created_at": datetime(2024, 1, 1, 5, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 5, 0, tzinfo=timezone.utc),
    },
]


def upgrade() -> None:
    """Seed data_sharing_agreements with inline rows.

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
