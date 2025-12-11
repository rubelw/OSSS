from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0174"
down_revision = "0173"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "meetings"

# Inline seed rows for meetings
# Columns:
# org_id, governing_body_id, committee_id, title, scheduled_at,
# starts_at, ends_at, location, status, is_public, stream_url,
# created_at, updated_at, id
SEED_ROWS = [
    {
        "org_id": "c201e5e9-60c0-466f-8f63-aecbf868c420",
        "governing_body_id": "4b9ddc27-7c2b-4b4b-8c9b-4d2f3f4c1234",
        "committee_id": "9f682e86-6e28-58d8-8aa7-70136e62f6e8",
        "title": "Finance Committee Planning Session",
        "scheduled_at": "2024-01-01T01:00:00Z",
        "starts_at": "2024-01-01T01:00:00Z",
        "ends_at": "2024-01-01T01:00:00Z",
        "location": "District Office Conference Room A",
        "status": "scheduled",
        "is_public": False,
        "stream_url": "https://meetings.example.org/internal/finance-planning-2024-01-01-01",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
        "id": "89ab8c9b-8c20-5b36-95db-e4e7e0a5e3b4",
    },
    {
        "org_id": "c201e5e9-60c0-466f-8f63-aecbf868c420",
        "governing_body_id": "4b9ddc27-7c2b-4b4b-8c9b-4d2f3f4c1234",
        "committee_id": "9f682e86-6e28-58d8-8aa7-70136e62f6e8",
        "title": "Regular Board of Education Meeting",
        "scheduled_at": "2024-01-01T02:00:00Z",
        "starts_at": "2024-01-01T02:00:00Z",
        "ends_at": "2024-01-01T02:00:00Z",
        "location": "District Office Board Room",
        "status": "completed",
        "is_public": True,
        "stream_url": "https://stream.example.org/board/regular-meeting-2024-01-01-02",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
        "id": "10c4eb55-b76f-5706-acd4-ded2d68e4d61",
    },
    {
        "org_id": "c201e5e9-60c0-466f-8f63-aecbf868c420",
        "governing_body_id": "4b9ddc27-7c2b-4b4b-8c9b-4d2f3f4c1234",
        "committee_id": "9f682e86-6e28-58d8-8aa7-70136e62f6e8",
        "title": "Policy Committee Work Session",
        "scheduled_at": "2024-01-01T03:00:00Z",
        "starts_at": "2024-01-01T03:00:00Z",
        "ends_at": "2024-01-01T03:00:00Z",
        "location": "District Office Conference Room B",
        "status": "cancelled",
        "is_public": False,
        "stream_url": "https://meetings.example.org/internal/policy-work-session-2024-01-01-03",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
        "id": "da4cb612-bd37-5818-bc2f-dfefc611152c",
    },
    {
        "org_id": "c201e5e9-60c0-466f-8f63-aecbf868c420",
        "governing_body_id": "4b9ddc27-7c2b-4b4b-8c9b-4d2f3f4c1234",
        "committee_id": "9f682e86-6e28-58d8-8aa7-70136e62f6e8",
        "title": "Facilities and Operations Committee Meeting",
        "scheduled_at": "2024-01-01T04:00:00Z",
        "starts_at": "2024-01-01T04:00:00Z",
        "ends_at": "2024-01-01T04:00:00Z",
        "location": "Maintenance Building Training Room",
        "status": "in_progress",
        "is_public": True,
        "stream_url": "https://stream.example.org/board/facilities-operations-2024-01-01-04",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
        "id": "545d0b6a-d1fa-5559-a1ed-e0a5bebffc9e",
    },
    {
        "org_id": "c201e5e9-60c0-466f-8f63-aecbf868c420",
        "governing_body_id": "4b9ddc27-7c2b-4b4b-8c9b-4d2f3f4c1234",
        "committee_id": "9f682e86-6e28-58d8-8aa7-70136e62f6e8",
        "title": "Community Town Hall on Student Achievement",
        "scheduled_at": "2024-01-01T05:00:00Z",
        "starts_at": "2024-01-01T05:00:00Z",
        "ends_at": "2024-01-01T05:00:00Z",
        "location": "Central High School Auditorium",
        "status": "scheduled",
        "is_public": False,
        "stream_url": "https://stream.example.org/community/town-hall-2024-01-01-05",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
        "id": "0dad1a69-58dc-5723-b481-959ff33419a6",
    },
]


def upgrade() -> None:
    """Load seed data for meetings from inline SEED_ROWS.

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
