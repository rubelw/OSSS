from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0151"
down_revision = "0150"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "test_administrations"

# Inline seed rows for test_administrations
# Columns: test_id, administration_date, school_id, created_at, updated_at, id
SEED_ROWS = [
    {
        "test_id": "e13c8240-a3ee-423b-8102-ab9fbceead13",
        "administration_date": "2024-01-02",
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
        "id": "7c7d27eb-fcca-5a03-8420-284434ccb699",
    },
    {
        "test_id": "e13c8240-a3ee-423b-8102-ab9fbceead13",
        "administration_date": "2024-01-03",
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
        "id": "39747cc2-9954-5afb-b271-f2bd8f354b46",
    },
    {
        "test_id": "e13c8240-a3ee-423b-8102-ab9fbceead13",
        "administration_date": "2024-01-04",
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
        "id": "fce3aef7-7715-5ddd-a1d7-7039a7d6d166",
    },
    {
        "test_id": "e13c8240-a3ee-423b-8102-ab9fbceead13",
        "administration_date": "2024-01-05",
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
        "id": "40cfa2ec-d7ca-5f7e-b918-52f7aa2f1e16",
    },
    {
        "test_id": "e13c8240-a3ee-423b-8102-ab9fbceead13",
        "administration_date": "2024-01-06",
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
        "id": "423068a5-1809-5123-9552-1021c1f9ec76",
    },
]


def upgrade() -> None:
    """Load seed data for test_administrations from inline SEED_ROWS.

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
        row = {}
        for col in table.columns:
            if col.name in raw_row:
                row[col.name] = raw_row[col.name]

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

    log.info("Inserted %s rows into %s from inline SEED_ROWS", inserted, TABLE_NAME)


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
