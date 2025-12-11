from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0096"
down_revision = "0095"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "spaces"


# Inline seed data
ROWS = [

    # High School Main Building – HS01
    {
        "floor_id": "f8e212b7-a5fe-5f06-994e-d21dce9f765f",
        "code": "HS-101",
        "name": "English Classroom",
        "space_type": "instructional",
        "area_sqft": 900,
        "capacity": 30,
        "attributes": {},
        "created_at": "2024-01-01T13:00:00Z",
        "updated_at": "2024-01-01T13:00:00Z",
        "building_id": "2fcc53b4-7367-5852-9afb-ffdecafad618",
        "id": "8b3aa9d0-8d1e-5d94-8c02-9eb3a38e7e88",
    },
    {
        "floor_id": "f8e212b7-a5fe-5f06-994e-d21dce9f765f",
        "code": "HS-101",
        "name": "Math Classroom",
        "space_type": "instructional",
        "area_sqft": 900,
        "capacity": 30,
        "attributes": {},
        "created_at": "2024-01-01T13:00:00Z",
        "updated_at": "2024-01-01T13:00:00Z",
        "building_id": "2fcc53b4-7367-5852-9afb-ffdecafad618",
        "id": "8b3aa9d0-8d1e-5d94-8c02-9eb3a38e7e89",
    }
]


def upgrade() -> None:
    """Load seed data for spaces from inline ROWS.

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
        log.info("No inline rows defined for %s; nothing to insert", TABLE_NAME)
        return

    inserted = 0
    for raw_row in ROWS:
        # Explicit nested transaction (SAVEPOINT)
        nested = bind.begin_nested()
        try:
            bind.execute(table.insert().values(**raw_row))
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

    log.info("Inserted %s rows into %s from inline seed data", inserted, TABLE_NAME)


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
