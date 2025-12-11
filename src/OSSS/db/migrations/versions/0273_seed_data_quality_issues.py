from __future__ import annotations

import logging
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0273"
down_revision = "0272"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "data_quality_issues"

# Inline seed rows with realistic values
SEED_ROWS = [
    {
        "id": "e213a953-5031-4146-ae65-fd9154a585f3",
        "entity_type": "student",
        "entity_id": "1ae5c0a9-8c48-5f0a-aa93-91e8886e55ea",
        "rule": "missing_guardian_contact",
        "severity": "high",
        "details": "Student has no primary guardian phone or email on file.",
        "detected_at": datetime(2024, 8, 11, 8, 0, tzinfo=timezone.utc),
        "created_at": datetime(2024, 1, 1, 1, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 1, 0, tzinfo=timezone.utc),
    },
    {
        "id": "48b44860-4d67-4e70-93b2-9e47e3bd990f",
        "entity_type": "student",
        "entity_id": "02551b71-24b5-5435-824c-6549ec08bc41",
        "rule": "duplicate_enrollment_record",
        "severity": "high",
        "details": "Student appears with multiple active enrollments for the same school year.",
        "detected_at": datetime(2024, 8, 12, 8, 0, tzinfo=timezone.utc),
        "created_at": datetime(2024, 1, 1, 2, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 2, 0, tzinfo=timezone.utc),
    },
    {
        "id": "2935c7bc-3aef-4f9e-8255-4b93ac5f2dd8",
        "entity_type": "student",
        "entity_id": "a030f1ed-6609-5efe-85e1-df0e3fe8e9bf",
        "rule": "invalid_date_of_birth",
        "severity": "medium",
        "details": "Student date of birth is outside expected range for K–12 enrollment.",
        "detected_at": datetime(2024, 8, 13, 8, 0, tzinfo=timezone.utc),
        "created_at": datetime(2024, 1, 1, 3, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 3, 0, tzinfo=timezone.utc),
    },
    {
        "id": "83af2c35-46c9-4bff-a222-a3e726c7c914",
        "entity_type": "student",
        "entity_id": "534c2d39-a6d9-5df7-a99e-b82b041fec65",
        "rule": "inconsistent_grade_level",
        "severity": "medium",
        "details": "Student grade level does not match expected value based on cohort and promotion history.",
        "detected_at": datetime(2024, 8, 14, 8, 0, tzinfo=timezone.utc),
        "created_at": datetime(2024, 1, 1, 4, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 4, 0, tzinfo=timezone.utc),
    },
    {
        "id": "0e9d5c94-d69d-4021-85ca-8f606dc4944f",
        "entity_type": "student",
        "entity_id": "c52ed227-9a8c-52ec-8335-5d3cd0c9291e",
        "rule": "missing_home_language",
        "severity": "medium",
        "details": "Student home language is not set; required for state reporting.",
        "detected_at": datetime(2024, 8, 15, 8, 0, tzinfo=timezone.utc),
        "created_at": datetime(2024, 1, 1, 5, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 5, 0, tzinfo=timezone.utc),
    },
]


def upgrade() -> None:
    """Seed data_quality_issues with inline rows.

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
