from __future__ import annotations

import logging
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0280"
down_revision = "0279"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "messages"

ADMIN_USER_ID = "79869e88-eb05-5023-b28e-d64582430541"

# Inline seed rows with realistic messages
SEED_ROWS = [
    {
        "id": "33a2fb0b-263b-5b89-9402-01fa0fdd5bf2",
        "sender_id": ADMIN_USER_ID,
        "channel": "email",
        "subject": "Welcome to the OSSS Staff Portal",
        "body": (
            "Your OSSS account has been created. You can now sign in to review student information, "
            "run reports, and manage data quality tasks assigned to you."
        ),
        "sent_at": datetime(2024, 1, 1, 1, 0, tzinfo=timezone.utc),
        "created_at": datetime(2024, 1, 1, 1, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 1, 0, tzinfo=timezone.utc),
    },
    {
        "id": "8c5c09f5-343a-5b09-af48-25bf7a9904f4",
        "sender_id": ADMIN_USER_ID,
        "channel": "in_app",
        "subject": "New data quality issues assigned",
        "body": (
            "Several new data quality issues have been assigned to you. "
            "Open the Data Quality dashboard to review missing guardian contacts and invalid addresses."
        ),
        "sent_at": datetime(2024, 1, 1, 2, 0, tzinfo=timezone.utc),
        "created_at": datetime(2024, 1, 1, 2, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 2, 0, tzinfo=timezone.utc),
    },
    {
        "id": "beff1ed7-bb92-5a34-ab91-4b02af0885fe",
        "sender_id": ADMIN_USER_ID,
        "channel": "email",
        "subject": "Payroll run posted to General Ledger",
        "body": (
            "The latest payroll run has been successfully posted to the General Ledger. "
            "You can review the journal entries in the Accounting module."
        ),
        "sent_at": datetime(2024, 1, 1, 3, 0, tzinfo=timezone.utc),
        "created_at": datetime(2024, 1, 1, 3, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 3, 0, tzinfo=timezone.utc),
    },
    {
        "id": "208aec7e-1cbf-5253-8615-dfc9966a229c",
        "sender_id": ADMIN_USER_ID,
        "channel": "sms",
        "subject": "Transportation route update",
        "body": (
            "Bus route updates have been published for the upcoming semester. "
            "Please review changes to stops and times before communicating with families."
        ),
        "sent_at": datetime(2024, 1, 1, 4, 0, tzinfo=timezone.utc),
        "created_at": datetime(2024, 1, 1, 4, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 4, 0, tzinfo=timezone.utc),
    },
    {
        "id": "57d149bd-9fbc-5ae1-a305-61183793f857",
        "sender_id": ADMIN_USER_ID,
        "channel": "email",
        "subject": "Assessment window opening reminder",
        "body": (
            "The winter assessment window opens next week. Ensure all new students are scheduled "
            "and accommodations are entered before the first testing day."
        ),
        "sent_at": datetime(2024, 1, 1, 5, 0, tzinfo=timezone.utc),
        "created_at": datetime(2024, 1, 1, 5, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 5, 0, tzinfo=timezone.utc),
    },
]


def upgrade() -> None:
    """Seed messages with inline rows.

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
