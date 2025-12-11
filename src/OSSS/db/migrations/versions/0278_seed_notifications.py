from __future__ import annotations

import logging
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0278"
down_revision = "0277"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "notifications"

USER_ID = "de036046-aeed-4e84-960c-07ca8f9b99b9"

# Inline seed rows with realistic notification events
SEED_ROWS = [
    {
        "id": "9f7008d3-0698-59be-b50e-6dac5172c867",
        "user_id": USER_ID,
        "type": "system_announcement",
        "payload": {
            "title": "Welcome to the OSSS portal",
            "message": "Your district account has been created. Review your profile and update contact information if needed.",
        },
        "read_at": datetime(2024, 1, 1, 1, 15, tzinfo=timezone.utc),
        "created_at": datetime(2024, 1, 1, 1, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 1, 15, tzinfo=timezone.utc),
    },
    {
        "id": "c3b171ad-3015-5f68-9f0f-d885148a3277",
        "user_id": USER_ID,
        "type": "data_quality_issue_assigned",
        "payload": {
            "issue_id": "e213a953-5031-4146-ae65-fd9154a585f3",
            "entity_type": "student",
            "severity": "high",
            "summary": "Student record missing primary guardian contact.",
        },
        "read_at": datetime(2024, 1, 1, 2, 10, tzinfo=timezone.utc),
        "created_at": datetime(2024, 1, 1, 2, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 2, 10, tzinfo=timezone.utc),
    },
    {
        "id": "0d35a940-4c2a-5259-a2c1-1f1e3aacaaef",
        "user_id": USER_ID,
        "type": "export_completed",
        "payload": {
            "export_name": "student_roster_nightly",
            "status": "success",
            "file_uri": "s3://district-data-exports/student_roster/2024/01/01/student_roster_2024-01-01T01-00-00Z.csv",
        },
        "read_at": datetime(2024, 1, 1, 3, 5, tzinfo=timezone.utc),
        "created_at": datetime(2024, 1, 1, 3, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 3, 5, tzinfo=timezone.utc),
    },
    {
        "id": "7c7d519d-1f76-5b51-9eae-be02796bfc57",
        "user_id": USER_ID,
        "type": "approval_granted",
        "payload": {
            "approval_id": "b10df5e0-1444-54d0-a072-d6f5785deb1c",
            "association_id": "b2a8c0a2-b34a-58ee-8f41-a3cecd20958c",
            "status": "active",
            "summary": "Data sharing agreement approval is now active.",
        },
        "read_at": None,  # still unread
        "created_at": datetime(2024, 1, 1, 4, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 4, 0, tzinfo=timezone.utc),
    },
    {
        "id": "052e83c4-ac66-5f11-8d0f-a2e35ad0ee7d",
        "user_id": USER_ID,
        "type": "payroll_run_completed",
        "payload": {
            "run_id": "819c27d6-6631-5854-81c8-ad5adaccffa5",
            "status": "posted",
            "total_employees": 1,
            "note": "Payroll run 2024-01-15 has been posted to the general ledger.",
        },
        "read_at": None,  # still unread
        "created_at": datetime(2024, 1, 1, 5, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 5, 0, tzinfo=timezone.utc),
    },
]


def upgrade() -> None:
    """Seed notifications with inline rows.

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
