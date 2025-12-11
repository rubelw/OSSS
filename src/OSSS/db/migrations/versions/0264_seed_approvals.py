from __future__ import annotations

import logging
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0264"
down_revision = "0263"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "approvals"

PROPOSAL_ID = "96bc433b-c25c-5870-80e2-b50df1bf1d66"

# Inline seed rows with realistic approval data
SEED_ROWS = [
    {
        # Active approval – long-lived association
        "id": "b10df5e0-1444-54d0-a072-d6f5785deb1c",
        "association_id": "b2a8c0a2-b34a-58ee-8f41-a3cecd20958c",
        "proposal_id": PROPOSAL_ID,
        "approved_at": datetime(2024, 1, 1, 13, 0, tzinfo=timezone.utc),
        "expires_at": datetime(2025, 1, 1, 13, 0, tzinfo=timezone.utc),
        "status": "active",
        "created_at": datetime(2024, 1, 1, 13, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 13, 0, tzinfo=timezone.utc),
    },
    {
        # Approval that has expired
        "id": "99e50d7a-6728-57da-b878-c68b0bc5edbc",
        "association_id": "f84d3ccf-b6cb-523d-ae0f-381aa1550d13",
        "proposal_id": PROPOSAL_ID,
        "approved_at": datetime(2023, 1, 1, 14, 0, tzinfo=timezone.utc),
        "expires_at": datetime(2023, 12, 31, 23, 59, tzinfo=timezone.utc),
        "status": "expired",
        "created_at": datetime(2023, 1, 1, 14, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2023, 12, 31, 23, 59, tzinfo=timezone.utc),
    },
    {
        # Approval that was explicitly revoked before expiry
        "id": "79129f28-8376-5487-98f1-8918519806ce",
        "association_id": "03a4b657-30fc-5bc6-a4f8-a3a8d81afb18",
        "proposal_id": PROPOSAL_ID,
        "approved_at": datetime(2023, 6, 1, 9, 0, tzinfo=timezone.utc),
        "expires_at": datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc),
        "status": "revoked",
        "created_at": datetime(2023, 6, 1, 9, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 5, 10, 30, tzinfo=timezone.utc),
    },
    {
        # Another active approval (e.g., renewed or separate association)
        "id": "a090d7b5-fcb8-5356-8f0f-3a52d4375b6d",
        "association_id": "f1b88270-8d95-5137-8d10-72c3b1ec6dbe",
        "proposal_id": PROPOSAL_ID,
        "approved_at": datetime(2024, 2, 1, 8, 30, tzinfo=timezone.utc),
        "expires_at": datetime(2026, 2, 1, 8, 30, tzinfo=timezone.utc),
        "status": "active",
        "created_at": datetime(2024, 2, 1, 8, 30, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 2, 1, 8, 30, tzinfo=timezone.utc),
    },
    {
        # Short-term approval that has since expired
        "id": "1c2634bb-93d7-5e04-b73f-0d652baf6021",
        "association_id": "f72ed908-20a7-543e-a673-745c4d01d2f0",
        "proposal_id": PROPOSAL_ID,
        "approved_at": datetime(2024, 3, 1, 15, 0, tzinfo=timezone.utc),
        "expires_at": datetime(2024, 6, 1, 15, 0, tzinfo=timezone.utc),
        "status": "expired",
        "created_at": datetime(2024, 3, 1, 15, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 6, 1, 15, 0, tzinfo=timezone.utc),
    },
]


def upgrade() -> None:
    """Seed approvals with inline rows.

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
        row = {
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

    log.info("Inserted %s rows into %s", inserted, TABLE_NAME)


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
