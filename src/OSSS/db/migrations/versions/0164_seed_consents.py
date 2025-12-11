from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0164"
down_revision = "0163"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "consents"

# Inline seed rows for consents
# Columns: person_id, consent_type, granted, effective_date,
#          expires_on, created_at, updated_at, id
# Updated with realistic consent types.
SEED_ROWS = [
    {
        "person_id": "a09b6c88-3418-40b5-9f14-77800af409f7",
        "consent_type": "Directory information release",
        "granted": False,
        "effective_date": "2024-01-02",
        "expires_on": "2024-01-02",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
        "id": "23d4be37-da38-543d-9a13-f7a876759931",
    },
    {
        "person_id": "a09b6c88-3418-40b5-9f14-77800af409f7",
        "consent_type": "Photo / video media release",
        "granted": True,
        "effective_date": "2024-01-03",
        "expires_on": "2024-01-03",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
        "id": "ef78de5f-46aa-50b0-b276-7bbad3c0fd0e",
    },
    {
        "person_id": "a09b6c88-3418-40b5-9f14-77800af409f7",
        "consent_type": "Technology acceptable use agreement",
        "granted": False,
        "effective_date": "2024-01-04",
        "expires_on": "2024-01-04",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
        "id": "be9fdc44-0ec0-5f19-8a5e-9f6832fb4be7",
    },
    {
        "person_id": "a09b6c88-3418-40b5-9f14-77800af409f7",
        "consent_type": "Local field trip permission",
        "granted": True,
        "effective_date": "2024-01-05",
        "expires_on": "2024-01-05",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
        "id": "3f06fe26-72e7-52bc-a925-e4f28d085516",
    },
    {
        "person_id": "a09b6c88-3418-40b5-9f14-77800af409f7",
        "consent_type": "Transportation consent – bus ridership",
        "granted": False,
        "effective_date": "2024-01-06",
        "expires_on": "2024-01-06",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
        "id": "ca9c211d-5797-533f-a36e-e3d5c1cb2399",
    },
]


def upgrade() -> None:
    """Load seed data for consents from inline SEED_ROWS.

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

    log.info("Inserted %s rows into %s from inline SEED_ROWS", inserted, TABLE_NAME)


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
