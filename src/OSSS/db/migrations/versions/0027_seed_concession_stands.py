from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "concession_stands"

# Only source data — we will drop all extra fields later
SEED_ROWS = [
    {
        "id": "2e75f487-2ef3-40bf-a9d2-489a24bb86f0",
        "name": "High School Stadium Concessions",
        "school_name": "High School Stadium",
    },
    {
        "id": "1376656d-8249-463b-8ad7-5b7e50870c84",
        "name": "Middle School Gym Concessions",
        "school_name": "Middle School Gym",
    },
    {
        "id": "c654edbe-80e5-4e8a-88c5-a3dbbb546bcb",
        "name": "Elementary North Concessions",
        "school_name": "Elementary North",
    },
    {
        "id": "b1060ab3-a93b-4d7a-a2fc-8aae402ef5b0",
        "name": "Elementary South Concessions",
        "school_name": "Elementary South",
    },
    {
        "id": "63da8937-d544-4f4b-84d4-e10f4afd5ebc",
        "name": "Aquatic Center Concessions",
        "school_name": "Aquatic Center",
    },
]


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(TABLE_NAME):
        log.warning("Table %s does not exist; skipping seed", TABLE_NAME)
        return

    metadata = sa.MetaData()
    table = sa.Table(TABLE_NAME, metadata, autoload_with=bind)

    inserted = 0

    for src in SEED_ROWS:
        row = {
            "id": src["id"],
            "name": src["name"],
            "location": src.get("school_name"),  # ONLY THIS gets mapped
        }

        # Explicit SAVEPOINT
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
                row,
            )

    log.info("Inserted %s concession stands", inserted)


def downgrade() -> None:
    pass
