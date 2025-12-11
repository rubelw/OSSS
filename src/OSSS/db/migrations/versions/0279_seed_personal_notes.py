from __future__ import annotations

import logging
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0279"
down_revision = "0278"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "personal_notes"

USER_ID = "de036046-aeed-4e84-960c-07ca8f9b99b9"

# Inline seed rows with realistic notes
SEED_ROWS = [
    {
        "id": "9b5f31e5-d68f-57d7-b770-bac1252e018c",
        "user_id": USER_ID,
        "entity_type": "student",
        "entity_id": "64243eea-fdf4-52dc-aeaa-477f8fe2c025",
        "text": "Prefers to be called 'Sam'. Becomes anxious in very loud environments; give a few extra minutes during transitions.",
        "created_at": datetime(2024, 1, 1, 1, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 1, 0, tzinfo=timezone.utc),
    },
    {
        "id": "13264eb2-f746-51ed-a6de-012a705f5654",
        "user_id": USER_ID,
        "entity_type": "student",
        "entity_id": "9d4b1c98-1006-5d98-b10c-6034f2f932e9",
        "text": "Guardian prefers email communication after 5pm; avoid phone calls during work hours unless urgent.",
        "created_at": datetime(2024, 1, 1, 2, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 2, 0, tzinfo=timezone.utc),
    },
    {
        "id": "ec257d28-945c-5a06-81ab-d38a5ed13fba",
        "user_id": USER_ID,
        "entity_type": "student",
        "entity_id": "3b58739a-eb17-5fa1-9a95-e89f2aa22edc",
        "text": "New to the district this year; still learning building layout. Pair with a peer helper for the first month.",
        "created_at": datetime(2024, 1, 1, 3, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 3, 0, tzinfo=timezone.utc),
    },
    {
        "id": "f17d710b-492d-5c38-b491-093ce810632d",
        "user_id": USER_ID,
        "entity_type": "family",
        "entity_id": "da54ddc9-2a4f-546a-8a3f-ff2cb388b4a5",
        "text": "Family has limited internet access at home; send important items both digitally and on paper when possible.",
        "created_at": datetime(2024, 1, 1, 4, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 4, 0, tzinfo=timezone.utc),
    },
    {
        "id": "75091cfd-d52d-5bde-b7a6-e2941d51bbf3",
        "user_id": USER_ID,
        "entity_type": "staff",
        "entity_id": "729a9312-4dc1-53db-9c2e-7d1b2ae5195b",
        "text": "Primary contact for data quality follow-ups. Prefers tickets to be assigned with clear deadlines and context.",
        "created_at": datetime(2024, 1, 1, 5, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 5, 0, tzinfo=timezone.utc),
    },
]


def upgrade() -> None:
    """Seed personal_notes with inline rows.

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
