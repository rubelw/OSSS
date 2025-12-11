from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0097"
down_revision = "0096"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "assets"


# Inline seed rows for the `assets` table
ROWS: list[dict] = [
    {
        "building_id": "2fcc53b4-7367-5852-9afb-ffdecafad618",
        "space_id": "8b3aa9d0-8d1e-5d94-8c02-9eb3a38e7e88",
        "parent_asset_id": None,
        "tag": "MS-101-PROJ-01",
        "serial_no": "SN-PROJ-2023-001",
        "manufacturer": "Epson",
        "model": "PowerLite X49",
        "category": "AV Equipment",
        "status": "active",
        "install_date": "2023-08-15",
        "warranty_expires_at": "2028-08-15",
        "expected_life_months": 120,
        "attributes": {},
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
        "id": "6c7a568b-721c-523d-b5c2-ce3fd6029630",
    }
]


def upgrade() -> None:
    """Load seed data for assets from inline ROWS list.

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

    if not ROWS:
        log.info("No inline rows defined for %s; skipping", TABLE_NAME)
        return

    inserted = 0
    for raw_row in ROWS:
        row: dict[str, object] = {}

        for col in table.columns:
            if col.name not in raw_row:
                continue
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

    log.info("Inserted %s rows into %s from inline data", inserted, TABLE_NAME)


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
