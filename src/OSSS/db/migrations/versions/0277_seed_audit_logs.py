from __future__ import annotations

import logging
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0277"
down_revision = "0276"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "audit_logs"

ADMIN_USER_ID = "79869e88-eb05-5023-b28e-d64582430541"

# Inline seed rows with realistic audit events
SEED_ROWS = [
    {
        # Admin user logs in to the system
        "id": "7f214a13-0b2e-5871-9974-de54b1bec8b5",
        "actor_id": ADMIN_USER_ID,
        "action": "user_login",
        "entity_type": "user",
        "entity_id": ADMIN_USER_ID,
        "metadata": {
            "ip_address": "192.168.1.10",
            "user_agent": "Mozilla/5.0",
            "result": "success",
        },
        "occurred_at": datetime(2024, 1, 1, 1, 0, tzinfo=timezone.utc),
        "created_at": datetime(2024, 1, 1, 1, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 1, 0, tzinfo=timezone.utc),
    },
    {
        # Admin updates a student profile
        "id": "55cd0f4f-7c60-5155-bdaa-0f03e5d3f7ed",
        "actor_id": ADMIN_USER_ID,
        "action": "update_student_profile",
        "entity_type": "student",
        "entity_id": "20a53274-3e2f-5b9a-97df-5d434ef17b4f",
        "metadata": {
            "fields_changed": ["address", "guardian_phone"],
            "source": "admin_portal",
        },
        "occurred_at": datetime(2024, 1, 1, 2, 0, tzinfo=timezone.utc),
        "created_at": datetime(2024, 1, 1, 2, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 2, 0, tzinfo=timezone.utc),
    },
    {
        # Admin creates a new enrollment record
        "id": "c91771df-6e1c-5bf3-a000-bf9ddcc64c0b",
        "actor_id": ADMIN_USER_ID,
        "action": "create_enrollment",
        "entity_type": "enrollment",
        "entity_id": "58ff7db9-087f-5755-b927-3ae0efccdac0",
        "metadata": {
            "school_year": "2024-2025",
            "grade_level": "06",
            "school_id": "MS-001",
        },
        "occurred_at": datetime(2024, 1, 1, 3, 0, tzinfo=timezone.utc),
        "created_at": datetime(2024, 1, 1, 3, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 3, 0, tzinfo=timezone.utc),
    },
    {
        # Admin changes a student schedule
        "id": "474b4c26-3ad7-5155-a773-8c144be72709",
        "actor_id": ADMIN_USER_ID,
        "action": "update_schedule",
        "entity_type": "schedule",
        "entity_id": "b3a9a06b-cb7c-5ef9-bb62-21a8027a6cb7",
        "metadata": {
            "operation": "section_change",
            "course_code": "MATH-7",
            "from_section": "MATH-7A",
            "to_section": "MATH-7C",
        },
        "occurred_at": datetime(2024, 1, 1, 4, 0, tzinfo=timezone.utc),
        "created_at": datetime(2024, 1, 1, 4, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 4, 0, tzinfo=timezone.utc),
    },
    {
        # Admin triggers an export run
        "id": "cf052c51-41dc-561a-afae-0a18907ec599",
        "actor_id": ADMIN_USER_ID,
        "action": "run_export",
        "entity_type": "export_run",
        "entity_id": "3d7e98ee-92ea-5795-a629-deb920ad71a3",
        "metadata": {
            "export_name": "student_roster_nightly",
            "status": "queued",
        },
        "occurred_at": datetime(2024, 1, 1, 5, 0, tzinfo=timezone.utc),
        "created_at": datetime(2024, 1, 1, 5, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 5, 0, tzinfo=timezone.utc),
    },
]


def upgrade() -> None:
    """Seed audit_logs with inline rows.

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
