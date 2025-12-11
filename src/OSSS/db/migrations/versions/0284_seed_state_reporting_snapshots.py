from __future__ import annotations

import logging
from datetime import datetime, date, timezone

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0284"
down_revision = "0283"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "state_reporting_snapshots"

# Inline, realistic seed data
# Assumes columns: as_of_date, scope, payload, created_at, updated_at, id
SEED_ROWS = [
    {
        "id": "2e0cde15-d649-4268-b4bc-4c0a2e1d1c96",
        "as_of_date": date(2024, 1, 2),
        "scope": "Certified Enrollment – Fall 2023",
        "payload": {
            "students_total": 3205,
            "students_k12": 3050,
            "students_pk": 155,
            "submission_window": "2023-10-01 to 2023-10-15",
        },
        "created_at": datetime(2024, 1, 1, 1, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 1, 5, tzinfo=timezone.utc),
    },
    {
        "id": "cb7d6f9f-89d6-4543-b507-7eb5eae03163",
        "as_of_date": date(2024, 1, 3),
        "scope": "Attendance Snapshot – First Semester 2023-24",
        "payload": {
            "attendance_rate_overall": 0.948,
            "attendance_rate_k8": 0.955,
            "attendance_rate_9_12": 0.932,
            "days_in_term": 88,
        },
        "created_at": datetime(2024, 1, 1, 2, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 2, 4, tzinfo=timezone.utc),
    },
    {
        "id": "699e1b41-ee1c-42c1-b4d7-b57d1a77fe10",
        "as_of_date": date(2024, 1, 4),
        "scope": "Special Education Count – December 1, 2023",
        "payload": {
            "students_served": 415,
            "least_restrictive_env_pct": 0.86,
            "indicator": "Child Count",
        },
        "created_at": datetime(2024, 1, 1, 3, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 3, 6, tzinfo=timezone.utc),
    },
    {
        "id": "0e9ab2c4-d55d-4091-97e0-57e9aeaf519e",
        "as_of_date": date(2024, 1, 5),
        "scope": "Staff Snapshot – 2023-24 Contracted Staff",
        "payload": {
            "fte_teachers": 185.75,
            "fte_paraprofessionals": 62.5,
            "fte_administrators": 9.0,
            "fte_other": 41.25,
        },
        "created_at": datetime(2024, 1, 1, 4, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 4, 7, tzinfo=timezone.utc),
    },
    {
        "id": "29650350-f5c5-4602-ba25-e544e645f517",
        "as_of_date": date(2024, 1, 6),
        "scope": "Graduation Cohort Snapshot – Class of 2023",
        "payload": {
            "cohort_size": 215,
            "graduates_on_time": 203,
            "dropouts": 4,
            "completers_other": 3,
            "grad_rate": 0.944,
        },
        "created_at": datetime(2024, 1, 1, 5, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 5, 8, tzinfo=timezone.utc),
    },
]


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion from Python value to appropriate DB value (kept for consistency)."""
    # For inline seeds we're already using proper Python types, so just pass through.
    return raw


def upgrade() -> None:
    """Seed state_reporting_snapshots with a few realistic state reporting snapshots.

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
        row = {}
        for col in table.columns:
            if col.name not in raw_row:
                continue
            row[col.name] = _coerce_value(col, raw_row[col.name])

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
