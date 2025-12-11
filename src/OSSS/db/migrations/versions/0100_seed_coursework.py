from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0100"
down_revision = "0099"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "coursework"

# NOTE: Values are strings on purpose – Postgres will cast them to the proper
# types (UUID, DATE, TIME, TIMESTAMP, FLOAT, ENUM, etc.) based on the column
# types defined in the table.
#
# Make sure your table schema matches these types, especially `course_id`
# (these values are UUIDs).
INLINE_ROWS = [
    {
        "user_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "course_id": "a4cddcde-b046-5dd4-8255-593ba99983c6",
        "topic_id": "7e95d92a-702a-50f0-8eb1-80d59c0a8fb1",
        "title": "coursework_title_1",
        "description": "coursework_description_1",
        "work_type": "ASSIGNMENT",
        "state": "PUBLISHED",
        "due_date": "2024-01-02",
        "due_time": "09:07:00",
        "max_points": "1",
        "creation_time": "2024-01-01T01:00:00Z",
        "update_time": "2024-01-01T01:00:00Z",
        "id": "ad4834b4-ecca-50ef-b359-ef9f4e862e99",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
    },
    {
        "user_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "course_id": "a4cddcde-b046-5dd4-8255-593ba99983c6",
        "topic_id": "7e95d92a-702a-50f0-8eb1-80d59c0a8fb1",
        "title": "coursework_title_2",
        "description": "coursework_description_2",
        "work_type": "SHORT_ANSWER_QUESTION",
        "state": "DRAFT",
        "due_date": "2024-01-03",
        "due_time": "10:14:00",
        "max_points": "2",
        "creation_time": "2024-01-01T02:00:00Z",
        "update_time": "2024-01-01T02:00:00Z",
        "id": "53b3ae03-590d-533d-9481-88c9d8b67b51",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
    },
    {
        "user_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "course_id": "a4cddcde-b046-5dd4-8255-593ba99983c6",
        "topic_id": "7e95d92a-702a-50f0-8eb1-80d59c0a8fb1",
        "title": "coursework_title_3",
        "description": "coursework_description_3",
        "work_type": "MULTIPLE_CHOICE_QUESTION",
        "state": "SCHEDULED",
        "due_date": "2024-01-04",
        "due_time": "11:21:00",
        "max_points": "3",
        "creation_time": "2024-01-01T03:00:00Z",
        "update_time": "2024-01-01T03:00:00Z",
        "id": "08cb3848-588e-5f74-839c-ee2d04d5071b",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
    },
    {
        "user_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "course_id": "a4cddcde-b046-5dd4-8255-593ba99983c6",
        "topic_id": "7e95d92a-702a-50f0-8eb1-80d59c0a8fb1",
        "title": "coursework_title_4",
        "description": "coursework_description_4",
        "work_type": "MATERIAL",
        "state": "PUBLISHED",
        "due_date": "2024-01-05",
        "due_time": "12:28:00",
        "max_points": "4",
        "creation_time": "2024-01-01T04:00:00Z",
        "update_time": "2024-01-01T04:00:00Z",
        "id": "ba09260b-63d1-5e5c-9652-e5bb86ade3d0",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
    },
    {
        "user_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "course_id": "a4cddcde-b046-5dd4-8255-593ba99983c6",
        "topic_id": "7e95d92a-702a-50f0-8eb1-80d59c0a8fb1",
        "title": "coursework_title_5",
        "description": "coursework_description_5",
        "work_type": "ASSIGNMENT",
        "state": "DRAFT",
        "due_date": "2024-01-06",
        "due_time": "13:35:00",
        "max_points": "5",
        "creation_time": "2024-01-01T05:00:00Z",
        "update_time": "2024-01-01T05:00:00Z",
        "id": "5d0211d6-2bd7-5413-b448-643ba9d0267f",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
    },
]


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion from inline data to appropriate Python value."""
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
            log.warning("Invalid boolean for %s.%s: %r; using NULL", TABLE_NAME, col.name, raw)
            return None
        return bool(raw)

    # Otherwise, pass raw through and let DB cast (UUID, DATE, TIME, etc.)
    return raw


def upgrade() -> None:
    """Load seed data for coursework from inline rows.

    Each row is inserted inside an explicit nested transaction (SAVEPOINT)
    so a failing row won't abort the whole migration transaction.
    """
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(TABLE_NAME):
        log.warning("Table %s does not exist; skipping seed", TABLE_NAME)
        return

    if not INLINE_ROWS:
        log.info("No inline rows defined for %s; nothing to insert", TABLE_NAME)
        return

    metadata = sa.MetaData()
    table = sa.Table(TABLE_NAME, metadata, autoload_with=bind)

    inserted = 0
    for raw_row in INLINE_ROWS:
        row = {}

        for col in table.columns:
            if col.name not in raw_row:
                continue
            raw_val = raw_row[col.name]
            value = _coerce_value(col, raw_val)
            row[col.name] = value

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

    log.info("Inserted %s rows into %s from inline seed data", inserted, TABLE_NAME)


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
