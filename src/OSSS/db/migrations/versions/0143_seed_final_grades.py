from __future__ import annotations

import csv  # kept for consistency with other migrations (unused now)
import logging
import os  # kept for consistency with other migrations (unused now)

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0143"
down_revision = "0142"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "final_grades"

# Inline seed data (replaces CSV file)
ROWS = [
    {
        "student_id": "d4f53e78-1012-5322-a4f3-4bca2efc51be",
        "section_id": "6e9f574f-c3ac-505d-baee-e525351b2788",
        "grading_period_id": "1c7f96a7-5faa-5492-a149-07298173122e",
        "numeric_grade": "1",
        "letter_grade": "final_grades_letter_grade_1",
        "credits_earned": "1",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
        "id": "bf962ce3-812f-5c23-bd27-4df1d7f3b146",
    },
    {
        "student_id": "d4f53e78-1012-5322-a4f3-4bca2efc51be",
        "section_id": "6e9f574f-c3ac-505d-baee-e525351b2788",
        "grading_period_id": "1c7f96a7-5faa-5492-a149-07298173122e",
        "numeric_grade": "2",
        "letter_grade": "final_grades_letter_grade_2",
        "credits_earned": "2",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
        "id": "f8816a43-a920-5b7a-927d-48621a5a220c",
    },
    {
        "student_id": "d4f53e78-1012-5322-a4f3-4bca2efc51be",
        "section_id": "6e9f574f-c3ac-505d-baee-e525351b2788",
        "grading_period_id": "1c7f96a7-5faa-5492-a149-07298173122e",
        "numeric_grade": "3",
        "letter_grade": "final_grades_letter_grade_3",
        "credits_earned": "3",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
        "id": "dd95b8c7-9d8d-5edd-8328-1baa8cc04211",
    },
    {
        "student_id": "d4f53e78-1012-5322-a4f3-4bca2efc51be",
        "section_id": "6e9f574f-c3ac-505d-baee-e525351b2788",
        "grading_period_id": "1c7f96a7-5faa-5492-a149-07298173122e",
        "numeric_grade": "4",
        "letter_grade": "final_grades_letter_grade_4",
        "credits_earned": "4",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
        "id": "d2805316-059f-54f6-a20b-333f70217153",
    },
    {
        "student_id": "d4f53e78-1012-5322-a4f3-4bca2efc51be",
        "section_id": "6e9f574f-c3ac-505d-baee-e525351b2788",
        "grading_period_id": "1c7f96a7-5faa-5492-a149-07298173122e",
        "numeric_grade": "5",
        "letter_grade": "final_grades_letter_grade_5",
        "credits_earned": "5",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
        "id": "d8d0f00d-dbe3-597b-923c-598f499fa976",
    },
]


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion from inline seed rows to appropriate Python value."""
    if raw == "" or raw is None:
        return None

    t = col.type

    # Boolean needs special handling because SQLAlchemy is strict
    if isinstance(t, sa.Boolean):
        if isinstance(raw, str):
            v = raw.strip().lower()
            if v in ("true", "t", "1", "yes", "y"):
                return True
            if v in ("false", "f", "0", "no", "n"):
                return False
            log.warning(
                "Invalid boolean for %s.%s: %r; using NULL",
                TABLE_NAME,
                col.name,
                raw,
            )
            return None
        return bool(raw)

    # Otherwise, pass raw through and let DB cast (UUID, numeric, timestamptz, etc.)
    return raw


def upgrade() -> None:
    """Seed fixed final_grades rows inline (no CSV file)."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(TABLE_NAME):
        log.warning("Table %s does not exist; skipping seed", TABLE_NAME)
        return

    metadata = sa.MetaData()
    table = sa.Table(TABLE_NAME, metadata, autoload_with=bind)

    if not ROWS:
        log.info("No inline rows for %s; skipping", TABLE_NAME)
        return

    inserted = 0
    for raw_row in ROWS:
        row: dict[str, object] = {}

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

    log.info("Inserted %s inline rows into %s", inserted, TABLE_NAME)


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
