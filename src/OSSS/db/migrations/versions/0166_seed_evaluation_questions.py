from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0166"
down_revision = "0165"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "evaluation_questions"

# Inline seed rows for evaluation_questions
# Columns: section_id, text, type, scale_min, scale_max, weight, id, created_at, updated_at
# Updated with realistic evaluation questions and type.
SEED_ROWS = [
    {
        "section_id": "7086aafb-4277-5f98-91c2-bd55e42e5149",
        "text": "Plans instruction aligned to grade-level standards and learning targets.",
        "type": "rubric_rating",
        "scale_min": 1,
        "scale_max": 1,
        "weight": 1,
        "id": "dcba710f-627a-57b7-a23f-ea6c128a822b",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
    },
    {
        "section_id": "7086aafb-4277-5f98-91c2-bd55e42e5149",
        "text": "Uses assessment data to monitor student progress and adjust instruction.",
        "type": "rubric_rating",
        "scale_min": 2,
        "scale_max": 2,
        "weight": 2,
        "id": "c00d0e46-281e-55dc-8777-20d85ea2ed19",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
    },
    {
        "section_id": "7086aafb-4277-5f98-91c2-bd55e42e5149",
        "text": "Creates a positive, respectful classroom environment that supports learning.",
        "type": "rubric_rating",
        "scale_min": 3,
        "scale_max": 3,
        "weight": 3,
        "id": "bfc4e1de-4ecb-5485-bccc-e99519d4db9d",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
    },
    {
        "section_id": "7086aafb-4277-5f98-91c2-bd55e42e5149",
        "text": "Engages students in higher-order thinking and problem-solving.",
        "type": "rubric_rating",
        "scale_min": 4,
        "scale_max": 4,
        "weight": 4,
        "id": "e1d66475-c116-5789-9ffe-0672a425fa20",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
    },
    {
        "section_id": "7086aafb-4277-5f98-91c2-bd55e42e5149",
        "text": "Collaborates with colleagues and families to support student success.",
        "type": "rubric_rating",
        "scale_min": 5,
        "scale_max": 5,
        "weight": 5,
        "id": "19705481-89ae-5706-81f8-81c1b1a2b5e6",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
    },
]


def upgrade() -> None:
    """Load seed data for evaluation_questions from inline SEED_ROWS.

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
