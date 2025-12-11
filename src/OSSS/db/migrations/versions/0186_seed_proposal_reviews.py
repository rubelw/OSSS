from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0186"
down_revision = "0185"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "proposal_reviews"

# Inline seed rows for proposal_reviews
# Columns:
# proposal_id, review_round_id, reviewer_id, decision, decided_at,
# comment, created_at, updated_at, id
SEED_ROWS = [
    {
        "proposal_id": "96bc433b-c25c-5870-80e2-b50df1bf1d66",
        "review_round_id": "4f0cdda3-ce2d-5928-97e9-d20ac96daa47",
        "reviewer_id": "a09b6c88-3418-40b5-9f14-77800af409f7",
        "decision": "approved",
        "decided_at": "2024-01-01T01:00:00Z",
        "comment": "Proposal meets all rubric criteria and is ready to move forward.",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
        "id": "54cc27e4-04e6-52e9-abad-7395507cc7a5",
    },
    {
        "proposal_id": "96bc433b-c25c-5870-80e2-b50df1bf1d66",
        "review_round_id": "4f0cdda3-ce2d-5928-97e9-d20ac96daa47",
        "reviewer_id": "a09b6c88-3418-40b5-9f14-77800af409f7",
        "decision": "approved_with_revisions",
        "decided_at": "2024-01-01T02:00:00Z",
        "comment": "Approved pending minor edits to the budget narrative and timeline.",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
        "id": "b556d935-32a3-5711-a552-c081db914d57",
    },
    {
        "proposal_id": "96bc433b-c25c-5870-80e2-b50df1bf1d66",
        "review_round_id": "4f0cdda3-ce2d-5928-97e9-d20ac96daa47",
        "reviewer_id": "a09b6c88-3418-40b5-9f14-77800af409f7",
        "decision": "revisions_requested",
        "decided_at": "2024-01-01T03:00:00Z",
        "comment": "Clarify alignment to district strategic priorities and add measurable outcomes.",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
        "id": "279e6bb5-10ef-57d8-8294-9fc9500d4e1e",
    },
    {
        "proposal_id": "96bc433b-c25c-5870-80e2-b50df1bf1d66",
        "review_round_id": "4f0cdda3-ce2d-5928-97e9-d20ac96daa47",
        "reviewer_id": "a09b6c88-3418-40b5-9f14-77800af409f7",
        "decision": "rejected",
        "decided_at": "2024-01-01T04:00:00Z",
        "comment": "Scope and cost are not feasible within the current funding cycle.",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
        "id": "4e982ed6-516a-54f7-bdb1-2294e6675ef9",
    },
    {
        "proposal_id": "96bc433b-c25c-5870-80e2-b50df1bf1d66",
        "review_round_id": "4f0cdda3-ce2d-5928-97e9-d20ac96daa47",
        "reviewer_id": "a09b6c88-3418-40b5-9f14-77800af409f7",
        "decision": "tabled",
        "decided_at": "2024-01-01T05:00:00Z",
        "comment": "Decision deferred pending additional information from the vendor.",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
        "id": "7e7fa416-0a80-5251-9387-0d9da8cca898",
    },
]


def upgrade() -> None:
    """Load seed data for proposal_reviews from inline SEED_ROWS.

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
