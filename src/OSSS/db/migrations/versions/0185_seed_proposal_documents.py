from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0185"
down_revision = "0184"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "proposal_documents"

# Inline seed rows for proposal_documents
# Columns: proposal_id, document_id, file_uri, label, created_at, updated_at, id
SEED_ROWS = [
    {
        "proposal_id": "96bc433b-c25c-5870-80e2-b50df1bf1d66",
        "document_id": "e0c6ecb5-af4d-5c1c-bc1b-bf266b3ba7d8",
        "file_uri": "https://files.example.org/proposals/96bc433b/original-submission.pdf",
        "label": "Original proposal packet",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
        "id": "f445d458-f4ce-5e38-96b8-692ea599a499",
    },
    {
        "proposal_id": "96bc433b-c25c-5870-80e2-b50df1bf1d66",
        "document_id": "e0c6ecb5-af4d-5c1c-bc1b-bf266b3ba7d8",
        "file_uri": "https://files.example.org/proposals/96bc433b/revised-scope-of-work.pdf",
        "label": "Revised scope of work",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
        "id": "6ae192b5-b5fa-58f7-8624-aa8bff3555c0",
    },
    {
        "proposal_id": "96bc433b-c25c-5870-80e2-b50df1bf1d66",
        "document_id": "e0c6ecb5-af4d-5c1c-bc1b-bf266b3ba7d8",
        "file_uri": "https://files.example.org/proposals/96bc433b/budget-workbook.xlsx",
        "label": "Detailed budget workbook",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
        "id": "8aa22599-f94e-549e-9ef3-1972d20991f4",
    },
    {
        "proposal_id": "96bc433b-c25c-5870-80e2-b50df1bf1d66",
        "document_id": "e0c6ecb5-af4d-5c1c-bc1b-bf266b3ba7d8",
        "file_uri": "https://files.example.org/proposals/96bc433b/vendor-w9.pdf",
        "label": "Vendor W-9 form",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
        "id": "40f5f053-2c61-5053-a6b4-a6365b9e5c1b",
    },
    {
        "proposal_id": "96bc433b-c25c-5870-80e2-b50df1bf1d66",
        "document_id": "e0c6ecb5-af4d-5c1c-bc1b-bf266b3ba7d8",
        "file_uri": "https://files.example.org/proposals/96bc433b/board-approval-resolution.pdf",
        "label": "Board approval resolution",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
        "id": "37bf6fd9-f3bf-53c6-a064-05f5142ec661",
    },
]


def upgrade() -> None:
    """Load seed data for proposal_documents from inline SEED_ROWS.

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
