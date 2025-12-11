from __future__ import annotations

import csv  # kept for consistency with other migrations (unused here)
import logging
import os  # kept for consistency with other migrations (unused here)

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0138"
down_revision = "0137"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "attendance_events"

# Inline seed data (replaces CSV)
ROWS = [
    {
        "student_id": "d4f53e78-1012-5322-a4f3-4bca2efc51be",
        "section_meeting_id": "00956f01-9289-53f6-bf82-5bfdc67ead94",
        "date": "2024-01-02",
        "code": "P",
        "minutes": "1",
        "notes": "attendance_events_notes_1",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
        "id": "8e494d70-996e-5d54-a371-c12b723a77de",
    },
    {
        "student_id": "d4f53e78-1012-5322-a4f3-4bca2efc51be",
        "section_meeting_id": "00956f01-9289-53f6-bf82-5bfdc67ead94",
        "date": "2024-01-03",
        "code": "P",
        "minutes": "2",
        "notes": "attendance_events_notes_2",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
        "id": "99c10635-7a0f-5b80-ad1b-fd71f9db39b8",
    },
    {
        "student_id": "d4f53e78-1012-5322-a4f3-4bca2efc51be",
        "section_meeting_id": "00956f01-9289-53f6-bf82-5bfdc67ead94",
        "date": "2024-01-04",
        "code": "P",
        "minutes": "3",
        "notes": "attendance_events_notes_3",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
        "id": "3843ef43-17f8-57fe-85dd-433a90a9a176",
    },
    {
        "student_id": "d4f53e78-1012-5322-a4f3-4bca2efc51be",
        "section_meeting_id": "00956f01-9289-53f6-bf82-5bfdc67ead94",
        "date": "2024-01-05",
        "code": "P",
        "minutes": "4",
        "notes": "attendance_events_notes_4",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
        "id": "bb16827a-3be6-5fc5-bcce-e3fdc5f8a00c",
    },
    {
        "student_id": "d4f53e78-1012-5322-a4f3-4bca2efc51be",
        "section_meeting_id": "00956f01-9289-53f6-bf82-5bfdc67ead94",
        "date": "2024-01-06",
        "code": "P",
        "minutes": "5",
        "notes": "attendance_events_notes_5",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
        "id": "f4f4712b-1b67-5215-9d57-61b2eceac21a",
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

    # Otherwise, pass raw through and let DB cast (UUID, date, timestamptz, int, etc.)
    return raw


def upgrade() -> None:
    """Seed fixed attendance_events rows inline (no CSV file)."""
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
            raw_val = raw_row[col.name]
            row[col.name] = _coerce_value(col, raw_val)

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
