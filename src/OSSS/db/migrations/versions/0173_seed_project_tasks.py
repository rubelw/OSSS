from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0173"
down_revision = "0172"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "project_tasks"

# Inline seed rows for project_tasks
# Columns:
# project_id, name, status, start_date, end_date, percent_complete,
# assignee_user_id, attributes, created_at, updated_at, id
SEED_ROWS = [
    {
        "project_id": "54bb3dda-4385-54bb-8939-0528dc95c1e2",
        "name": "Define project scope and success criteria",
        "status": "Not started",
        "start_date": "2024-01-02",
        "end_date": "2024-01-02",
        "percent_complete": 1,
        "assignee_user_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "attributes": {},
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
        "id": "0922bb2f-9d29-5fa2-b15b-33a1c0551ae2",
    },
    {
        "project_id": "54bb3dda-4385-54bb-8939-0528dc95c1e2",
        "name": "Meet with stakeholders to gather requirements",
        "status": "In progress",
        "start_date": "2024-01-03",
        "end_date": "2024-01-03",
        "percent_complete": 2,
        "assignee_user_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "attributes": {},
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
        "id": "77627cbc-6d39-54a8-b13d-64d09fbefb0c",
    },
    {
        "project_id": "54bb3dda-4385-54bb-8939-0528dc95c1e2",
        "name": "Design data model and integration points",
        "status": "In progress",
        "start_date": "2024-01-04",
        "end_date": "2024-01-04",
        "percent_complete": 3,
        "assignee_user_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "attributes": {},
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
        "id": "a77b6fa4-f03d-5aff-82a3-1b07911436d7",
    },
    {
        "project_id": "54bb3dda-4385-54bb-8939-0528dc95c1e2",
        "name": "Implement core features and initial workflows",
        "status": "In review",
        "start_date": "2024-01-05",
        "end_date": "2024-01-05",
        "percent_complete": 4,
        "assignee_user_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "attributes": {},
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
        "id": "e5a1a3da-3db7-5234-991b-ffcbc043e16b",
    },
    {
        "project_id": "54bb3dda-4385-54bb-8939-0528dc95c1e2",
        "name": "Deploy to staging and collect user feedback",
        "status": "Completed",
        "start_date": "2024-01-06",
        "end_date": "2024-01-06",
        "percent_complete": 5,
        "assignee_user_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "attributes": {},
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
        "id": "97f15c39-4bdb-58b2-9847-f519375bf0e6",
    },
]


def upgrade() -> None:
    """Load seed data for project_tasks from inline SEED_ROWS.

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

    log.info(
        "Inserted %s rows into %s from inline SEED_ROWS",
        inserted,
        TABLE_NAME,
    )


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
