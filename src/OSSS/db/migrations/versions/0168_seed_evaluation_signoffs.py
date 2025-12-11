from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0168"
down_revision = "0167"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "evaluation_signoffs"

# Inline seed rows for evaluation_signoffs
# Columns: note, assignment_id, signer_id, signed_at, id, created_at, updated_at
# Updated with realistic signoff notes.
SEED_ROWS = [
    {
        "note": "Evaluator sign-off: Formal observation completed and shared with teacher.",
        "assignment_id": "a5d5a408-430c-57f7-941a-9bd0d8ed9049",
        "signer_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "signed_at": "2024-01-01T01:00:00Z",
        "id": "b459c296-fa9a-507c-8edb-fe872f81dbbd",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
    },
    {
        "note": "Teacher sign-off: I have reviewed the ratings and comments.",
        "assignment_id": "a5d5a408-430c-57f7-941a-9bd0d8ed9049",
        "signer_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "signed_at": "2024-01-01T02:00:00Z",
        "id": "b68c6afa-7bd5-5d8e-88ea-0f9627e467d8",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
    },
    {
        "note": "Teacher acknowledgement: Sign-off indicates receipt, not agreement with all ratings.",
        "assignment_id": "a5d5a408-430c-57f7-941a-9bd0d8ed9049",
        "signer_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "signed_at": "2024-01-01T03:00:00Z",
        "id": "a3a9599c-0579-5291-884f-8002af265007",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
    },
    {
        "note": "Administrator sign-off: Post-conference held and next steps documented.",
        "assignment_id": "a5d5a408-430c-57f7-941a-9bd0d8ed9049",
        "signer_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "signed_at": "2024-01-01T04:00:00Z",
        "id": "8d236fd8-67d1-54ef-b7a7-f870a4ba1509",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
    },
    {
        "note": "Final sign-off: Evaluation cycle for this assignment is complete.",
        "assignment_id": "a5d5a408-430c-57f7-941a-9bd0d8ed9049",
        "signer_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "signed_at": "2024-01-01T05:00:00Z",
        "id": "f0497ea7-fb98-5405-b3fc-c3589c6a2581",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
    },
]


def upgrade() -> None:
    """Load seed data for evaluation_signoffs from inline SEED_ROWS.

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

    log.info(
        "Inserted %s rows into %s from inline SEED_ROWS",
        inserted,
        TABLE_NAME,
    )


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
