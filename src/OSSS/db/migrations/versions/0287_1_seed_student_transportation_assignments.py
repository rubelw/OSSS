from __future__ import annotations

import logging
from datetime import datetime, date, timezone

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0287_1"
down_revision = "0287"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "student_transportation_assignments"

# Inline, realistic seed data
# Columns: student_id, route_id, stop_id, direction, effective_start,
#          effective_end, created_at, updated_at, id
SEED_ROWS = [
    {
        # Morning assignment for fall semester
        "id": "86f29e9f-9e38-5515-abeb-05f3bd6536a2",
        "student_id": "d4f53e78-1012-5322-a4f3-4bca2efc51be",
        "route_id": "dc004672-2936-552e-831b-4e2516959a9e",
        "stop_id": "c6715e2f-3d54-5193-913a-112e1faadb14",
        "direction": "AM",
        "effective_start": date(2024, 8, 23),   # first day of school
        "effective_end": date(2024, 12, 20),    # end of fall semester
        "created_at": datetime(2024, 8, 1, 1, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 8, 1, 1, 0, tzinfo=timezone.utc),
    },
    {
        # Afternoon assignment for fall semester
        "id": "c5bae01b-a98b-57dd-8b38-c4557ea0b1a9",
        "student_id": "d4f53e78-1012-5322-a4f3-4bca2efc51be",
        "route_id": "dc004672-2936-552e-831b-4e2516959a9e",
        "stop_id": "c6715e2f-3d54-5193-913a-112e1faadb14",
        "direction": "PM",
        "effective_start": date(2024, 8, 23),
        "effective_end": date(2024, 12, 20),
        "created_at": datetime(2024, 8, 1, 2, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 8, 1, 2, 0, tzinfo=timezone.utc),
    },
    {
        # Morning assignment for spring term (same route/stop)
        "id": "69deab03-0c9e-59b3-b23b-cf7d83595a92",
        "student_id": "d4f53e78-1012-5322-a4f3-4bca2efc51be",
        "route_id": "dc004672-2936-552e-831b-4e2516959a9e",
        "stop_id": "c6715e2f-3d54-5193-913a-112e1faadb14",
        "direction": "AM",
        "effective_start": date(2025, 1, 6),    # first day after winter break
        "effective_end": date(2025, 5, 30),     # end of school year
        "created_at": datetime(2024, 8, 1, 3, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 8, 1, 3, 0, tzinfo=timezone.utc),
    },
    {
        # Afternoon assignment for spring term
        "id": "08b35561-1a05-51c9-8dea-955018bbda27",
        "student_id": "d4f53e78-1012-5322-a4f3-4bca2efc51be",
        "route_id": "dc004672-2936-552e-831b-4e2516959a9e",
        "stop_id": "c6715e2f-3d54-5193-913a-112e1faadb14",
        "direction": "PM",
        "effective_start": date(2025, 1, 6),
        "effective_end": date(2025, 5, 30),
        "created_at": datetime(2024, 8, 1, 4, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 8, 1, 4, 0, tzinfo=timezone.utc),
    },
    {
        # Midday shuttle assignment (e.g., to a program or shared campus)
        "id": "26f727ab-35d5-568e-9108-add2af8a08bf",
        "student_id": "d4f53e78-1012-5322-a4f3-4bca2efc51be",
        "route_id": "dc004672-2936-552e-831b-4e2516959a9e",
        "stop_id": "c6715e2f-3d54-5193-913a-112e1faadb14",
        "direction": "Midday Shuttle",
        "effective_start": date(2024, 9, 3),    # starts after schedule change
        "effective_end": date(2024, 12, 20),
        "created_at": datetime(2024, 8, 1, 5, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 8, 1, 5, 0, tzinfo=timezone.utc),
    },
]


def _coerce_value(col: sa.Column, raw):
    """For inline seeds we already use appropriate Python types."""
    return raw


def upgrade() -> None:
    """Seed student_transportation_assignments with realistic example rows."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(TABLE_NAME):
        log.warning("Table %s does not exist; skipping seed", TABLE_NAME)
        return

    metadata = sa.MetaData()
    table = sa.Table(TABLE_NAME, metadata, autoload_with=bind)

    inserted = 0
    for raw_row in SEED_ROWS:
        row = {}

        # Only include keys that are actual columns
        for col in table.columns:
            if col.name not in raw_row:
                continue
            row[col.name] = _coerce_value(col, raw_row[col.name])

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
