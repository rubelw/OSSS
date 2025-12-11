from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0152"
down_revision = "0151"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "test_results"

# Inline seed rows for test_results
# Columns: administration_id, student_id, scale_score, percentile,
#          performance_level, created_at, updated_at, id
# Updated to use more realistic performance_level names.
SEED_ROWS = [
    {
        "administration_id": "7c7d27eb-fcca-5a03-8420-284434ccb699",
        "student_id": "d4f53e78-1012-5322-a4f3-4bca2efc51be",
        "scale_score": 1,
        "percentile": 1,
        "performance_level": "Did not meet expectations",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
        "id": "d8694a37-e72c-5d8f-8e9a-7cb81bcfe2f5",
    },
    {
        "administration_id": "7c7d27eb-fcca-5a03-8420-284434ccb699",
        "student_id": "d4f53e78-1012-5322-a4f3-4bca2efc51be",
        "scale_score": 2,
        "percentile": 2,
        "performance_level": "Partially met expectations",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
        "id": "0f50207c-41cc-57d6-a1fe-9d58ac8771d2",
    },
    {
        "administration_id": "7c7d27eb-fcca-5a03-8420-284434ccb699",
        "student_id": "d4f53e78-1012-5322-a4f3-4bca2efc51be",
        "scale_score": 3,
        "percentile": 3,
        "performance_level": "Approaching proficiency",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
        "id": "6d7c73ca-e9e3-58e3-a39a-caffa0998734",
    },
    {
        "administration_id": "7c7d27eb-fcca-5a03-8420-284434ccb699",
        "student_id": "d4f53e78-1012-5322-a4f3-4bca2efc51be",
        "scale_score": 4,
        "percentile": 4,
        "performance_level": "Proficient",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
        "id": "4e59e69e-6b10-5c72-b283-582a6508b6b0",
    },
    {
        "administration_id": "7c7d27eb-fcca-5a03-8420-284434ccb699",
        "student_id": "d4f53e78-1012-5322-a4f3-4bca2efc51be",
        "scale_score": 5,
        "percentile": 5,
        "performance_level": "Advanced",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
        "id": "0e6e1fd0-da0d-50af-960a-66aa6b0f2d35",
    },
]


def upgrade() -> None:
    """Load seed data for test_results from inline SEED_ROWS.

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
