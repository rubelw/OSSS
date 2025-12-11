from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0189"
down_revision = "0188"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "round_decisions"

# Inline seed rows for round_decisions
# Columns:
# review_round_id, decision, decided_at, notes,
# id, created_at, updated_at
SEED_ROWS = [
    {
        "review_round_id": "4f0cdda3-ce2d-5928-97e9-d20ac96daa47",
        "decision": "approved",
        "decided_at": "2024-01-01T01:00:00Z",
        "notes": "Approved without conditions; proposal meets all rubric criteria for alignment and rigor.",
        "id": "4f496d02-932d-5962-adfc-802a702352ee",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
    },
    {
        "review_round_id": "212abf9b-9751-5c16-954c-1c1ef2a53602",
        "decision": "approved_with_conditions",
        "decided_at": "2024-01-01T02:00:00Z",
        "notes": "Approved with conditions; implement recommended assessment revisions prior to adoption.",
        "id": "034a8685-1187-5044-95b4-8deadb28b1a7",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
    },
    {
        "review_round_id": "81542e6f-ca63-568e-97a2-221a0e92bd95",
        "decision": "revisions_requested",
        "decided_at": "2024-01-01T03:00:00Z",
        "notes": "Revisions requested; clarify alignment to state standards and expand instructional supports.",
        "id": "4257c22e-3eec-509d-9184-5e59aed135ca",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
    },
    {
        "review_round_id": "0ffc2535-c10a-547b-9ced-eb66953db289",
        "decision": "rejected",
        "decided_at": "2024-01-01T04:00:00Z",
        "notes": "Rejected; proposal lacks sufficient evidence of standards alignment and instructional coherence.",
        "id": "588c8467-15d2-578e-b8ae-45d322111c00",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
    },
    {
        "review_round_id": "08d55fa9-449f-5cfe-8cf1-735c8b98547e",
        "decision": "approved",
        "decided_at": "2024-01-01T05:00:00Z",
        "notes": "Approved after follow-up review; all prior conditions have been satisfactorily addressed.",
        "id": "3e57eaa8-dd12-51f7-be9b-45d1d702a615",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
    },
]


def upgrade() -> None:
    """Load seed data for round_decisions from inline SEED_ROWS.

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
