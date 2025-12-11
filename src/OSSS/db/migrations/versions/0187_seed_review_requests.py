from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0187"
down_revision = "0186"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "review_requests"

# Inline seed rows for review_requests
# Columns:
# curriculum_version_id, association_id, status, submitted_at, decided_at,
# notes, created_at, updated_at, id
SEED_ROWS = [
    {
        "curriculum_version_id": "8d122c3e-38cb-5f27-a63e-facf99bd4c49",
        "association_id": "d611575d-a62c-41a1-a157-6434d34ffd8f",
        "status": "submitted",
        "submitted_at": "2024-01-01T01:00:00Z",
        "decided_at": "2024-01-01T01:00:00Z",
        "notes": "Initial alignment review request submitted by curriculum team.",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
        "id": "e2ed5287-c43e-5133-997f-df9c2c704560",
    },
    {
        "curriculum_version_id": "8d122c3e-38cb-5f27-a63e-facf99bd4c49",
        "association_id": "d611575d-a62c-41a1-a157-6434d34ffd8f",
        "status": "in_review",
        "submitted_at": "2024-01-01T02:00:00Z",
        "decided_at": "2024-01-01T02:00:00Z",
        "notes": "Request routed to state reviewer; materials are under active review.",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
        "id": "8b0e80e0-e153-5ffb-99b7-1add6af893e3",
    },
    {
        "curriculum_version_id": "8d122c3e-38cb-5f27-a63e-facf99bd4c49",
        "association_id": "d611575d-a62c-41a1-a157-6434d34ffd8f",
        "status": "revisions_requested",
        "submitted_at": "2024-01-01T03:00:00Z",
        "decided_at": "2024-01-01T03:00:00Z",
        "notes": "Reviewer requested additional evidence for assessment alignment and pacing.",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
        "id": "5a7e0fa2-82b8-58fa-ad9e-2acad06b1c1d",
    },
    {
        "curriculum_version_id": "8d122c3e-38cb-5f27-a63e-facf99bd4c49",
        "association_id": "d611575d-a62c-41a1-a157-6434d34ffd8f",
        "status": "approved",
        "submitted_at": "2024-01-01T04:00:00Z",
        "decided_at": "2024-01-01T04:00:00Z",
        "notes": "Review committee approved the request; alignment letter will be issued.",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
        "id": "b9e6caa3-4681-53b8-a96a-097d20527c76",
    },
    {
        "curriculum_version_id": "8d122c3e-38cb-5f27-a63e-facf99bd4c49",
        "association_id": "d611575d-a62c-41a1-a157-6434d34ffd8f",
        "status": "closed",
        "submitted_at": "2024-01-01T05:00:00Z",
        "decided_at": "2024-01-01T05:00:00Z",
        "notes": "Request closed after final approval and communication to the vendor.",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
        "id": "6279f7fa-2665-55f3-8a8a-f2247e852a49",
    },
]


def upgrade() -> None:
    """Load seed data for review_requests from inline SEED_ROWS.

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
        row: dict[str, object] = {
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

    log.info(
        "Inserted %s rows into %s from inline SEED_ROWS",
        inserted,
        TABLE_NAME,
    )


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
