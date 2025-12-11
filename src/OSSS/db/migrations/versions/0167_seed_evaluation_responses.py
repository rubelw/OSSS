from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0167"
down_revision = "0166"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "evaluation_responses"

# Inline seed rows for evaluation_responses
# Columns: assignment_id, question_id, value_num, value_text,
#          comment, answered_at, id, created_at, updated_at
# Updated with realistic rubric responses and comments.
SEED_ROWS = [
    {
        "assignment_id": "a5d5a408-430c-57f7-941a-9bd0d8ed9049",
        "question_id": "dcba710f-627a-57b7-a23f-ea6c128a822b",
        "value_num": 1,
        "value_text": "Does not meet expectations",
        "comment": "Lesson plan did not clearly reference grade-level standards.",
        "answered_at": "2024-01-01T01:00:00Z",
        "id": "92b39673-de57-55e3-a900-467501f6915a",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
    },
    {
        "assignment_id": "a5d5a408-430c-57f7-941a-9bd0d8ed9049",
        "question_id": "dcba710f-627a-57b7-a23f-ea6c128a822b",
        "value_num": 2,
        "value_text": "Partially meets expectations",
        "comment": "Some objectives aligned, but success criteria were unclear.",
        "answered_at": "2024-01-01T02:00:00Z",
        "id": "1a3be265-fd30-5930-8f37-eeaaef15c9cb",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
    },
    {
        "assignment_id": "a5d5a408-430c-57f7-941a-9bd0d8ed9049",
        "question_id": "dcba710f-627a-57b7-a23f-ea6c128a822b",
        "value_num": 3,
        "value_text": "Meets expectations",
        "comment": "Objectives, tasks, and assessments were generally aligned.",
        "answered_at": "2024-01-01T03:00:00Z",
        "id": "fe67b637-e541-5a44-936f-17df59b9d1a5",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
    },
    {
        "assignment_id": "a5d5a408-430c-57f7-941a-9bd0d8ed9049",
        "question_id": "dcba710f-627a-57b7-a23f-ea6c128a822b",
        "value_num": 4,
        "value_text": "Exceeds expectations",
        "comment": "Strong alignment with clear checks for understanding built in.",
        "answered_at": "2024-01-01T04:00:00Z",
        "id": "67bf677d-69cc-5776-9dd2-4ccbfe753005",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
    },
    {
        "assignment_id": "a5d5a408-430c-57f7-941a-9bd0d8ed9049",
        "question_id": "dcba710f-627a-57b7-a23f-ea6c128a822b",
        "value_num": 5,
        "value_text": "Distinguished practice",
        "comment": "Highly aligned lesson with multiple differentiated paths and clear evidence of prior data use.",
        "answered_at": "2024-01-01T05:00:00Z",
        "id": "63ca1b5c-adf4-56f8-9cc2-bcaddba6692f",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
    },
]


def upgrade() -> None:
    """Load seed data for evaluation_responses from inline SEED_ROWS.

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
