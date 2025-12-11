from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0169"
down_revision = "0168"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "evaluation_reports"

# Inline seed rows for evaluation_reports
# Columns: cycle_id, scope, generated_at, file_id, id, created_at, updated_at
# Updated with realistic JSON scopes describing what the report includes.
SEED_ROWS = [
    {
        "cycle_id": "5997aacd-a6e7-500a-add0-ef0b4a81700e",
        "scope": {
            "report_type": "summative_evaluation",
            "include_sections": ["overall_ratings", "final_comments", "next_steps"],
        },
        "generated_at": "2024-01-01T01:00:00Z",
        "file_id": "39ca63db-2221-5408-ad28-c6dfaac3056d",
        "id": "f1118bb6-66b1-57db-811b-1dbcfa6118c5",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
    },
    {
        "cycle_id": "5997aacd-a6e7-500a-add0-ef0b4a81700e",
        "scope": {
            "report_type": "formative_check_in",
            "include_sections": ["observation_notes", "evidence_log"],
        },
        "generated_at": "2024-01-01T02:00:00Z",
        "file_id": "39ca63db-2221-5408-ad28-c6dfaac3056d",
        "id": "fe16373f-4070-5030-a517-97328204056a",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
    },
    {
        "cycle_id": "5997aacd-a6e7-500a-add0-ef0b4a81700e",
        "scope": {
            "report_type": "midyear_review",
            "include_sections": ["ratings_summary", "growth_goals", "progress_updates"],
        },
        "generated_at": "2024-01-01T03:00:00Z",
        "file_id": "39ca63db-2221-5408-ad28-c6dfaac3056d",
        "id": "7a95d785-8548-5ad5-852c-9e33c8343860",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
    },
    {
        "cycle_id": "5997aacd-a6e7-500a-add0-ef0b4a81700e",
        "scope": {
            "report_type": "observation_packet",
            "include_sections": ["formal_observations", "walkthroughs", "artifacts"],
        },
        "generated_at": "2024-01-01T04:00:00Z",
        "file_id": "39ca63db-2221-5408-ad28-c6dfaac3056d",
        "id": "7e7b6915-7d10-568c-9edf-25fb834e10f5",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
    },
    {
        "cycle_id": "5997aacd-a6e7-500a-add0-ef0b4a81700e",
        "scope": {
            "report_type": "end_of_cycle_archive",
            "include_sections": [
                "overall_ratings",
                "all_observations",
                "final_signoffs",
            ],
        },
        "generated_at": "2024-01-01T05:00:00Z",
        "file_id": "39ca63db-2221-5408-ad28-c6dfaac3056d",
        "id": "44e0f4b2-7d07-5d81-b85c-8d7741269047",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
    },
]


def upgrade() -> None:
    """Load seed data for evaluation_reports from inline SEED_ROWS.

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
