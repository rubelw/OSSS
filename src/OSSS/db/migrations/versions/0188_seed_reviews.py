from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0188"
down_revision = "0187"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "reviews"

# Inline seed rows for reviews
# Columns:
# review_round_id, reviewer_id, status, submitted_at, content,
# id, created_at, updated_at
SEED_ROWS = [
    {
        "review_round_id": "4f0cdda3-ce2d-5928-97e9-d20ac96daa47",
        "reviewer_id": "81e33e29-9cf8-4e8f-be57-ee83e0ef6bca",
        "status": "draft",
        "submitted_at": "2024-01-01T01:00:00Z",
        "content": (
            '{"summary": "Initial notes on curriculum alignment.", '
            '"strengths": ["Clear learning targets", "Well-scaffolded units"], '
            '"concerns": ["Need more formative assessment examples"], '
            '"overall_rating": "pending"}'
        ),
        "id": "9e407e71-f80b-56ba-892a-d6fa1290a0e3",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
    },
    {
        "review_round_id": "4f0cdda3-ce2d-5928-97e9-d20ac96daa47",
        "reviewer_id": "81e33e29-9cf8-4e8f-be57-ee83e0ef6bca",
        "status": "submitted",
        "submitted_at": "2024-01-01T02:00:00Z",
        "content": (
            '{"summary": "Formal review submitted.", '
            '"strengths": ["Standards clearly referenced", "Strong literacy integration"], '
            '"concerns": ["Limited support for multilingual learners"], '
            '"overall_rating": "meets_expectations"}'
        ),
        "id": "44cd937f-7bfd-547e-902a-6bec818313a4",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
    },
    {
        "review_round_id": "4f0cdda3-ce2d-5928-97e9-d20ac96daa47",
        "reviewer_id": "81e33e29-9cf8-4e8f-be57-ee83e0ef6bca",
        "status": "draft",
        "submitted_at": "2024-01-01T03:00:00Z",
        "content": (
            '{"summary": "Follow-up draft with additional feedback.", '
            '"strengths": ["Revised assessments show better alignment"], '
            '"concerns": ["Pacing for Semester 2 may be aggressive"], '
            '"overall_rating": "pending"}'
        ),
        "id": "66afc552-2c65-542c-9305-84724b5bcb88",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
    },
    {
        "review_round_id": "4f0cdda3-ce2d-5928-97e9-d20ac96daa47",
        "reviewer_id": "81e33e29-9cf8-4e8f-be57-ee83e0ef6bca",
        "status": "submitted",
        "submitted_at": "2024-01-01T04:00:00Z",
        "content": (
            '{"summary": "Updated review after revisions.", '
            '"strengths": ["Improved checks for understanding", "Clearer rubric language"], '
            '"concerns": ["Need examples for enrichment pathways"], '
            '"overall_rating": "exceeds_expectations"}'
        ),
        "id": "e95075e8-bc4d-50be-b6b5-1c918d7bfe53",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
    },
    {
        "review_round_id": "4f0cdda3-ce2d-5928-97e9-d20ac96daa47",
        "reviewer_id": "81e33e29-9cf8-4e8f-be57-ee83e0ef6bca",
        "status": "draft",
        "submitted_at": "2024-01-01T05:00:00Z",
        "content": (
            '{"summary": "Internal draft capturing final committee comments.", '
            '"strengths": ["Comprehensive unit overviews", "Strong vertical alignment"], '
            '"concerns": ["Professional learning plan still in development"], '
            '"overall_rating": "pending"}'
        ),
        "id": "ee6142af-1e65-5b10-87e4-f0fc0cdd22a8",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
    },
]


def upgrade() -> None:
    """Load seed data for reviews from inline SEED_ROWS.

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
