from __future__ import annotations

import csv  # kept for consistency with other migrations (unused now)
import logging
import os  # kept for consistency with other migrations (unused now)

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0142"
down_revision = "0140"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "gradebook_entries"

# Inline seed data (replaces CSV file)
ROWS = [
    {
        "assignment_id": "0e5a804a-8bcd-5711-8e93-1fa2cc7bf006",
        "student_id": "d4f53e78-1012-5322-a4f3-4bca2efc51be",
        "score": "1",
        "submitted_at": "2024-01-01T01:00:00Z",
        "late": "gradebook_entries_late_1",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
        "id": "89fc330e-732e-58ec-b616-02201c080f92",
    },
    {
        "assignment_id": "0e5a804a-8bcd-5711-8e93-1fa2cc7bf006",
        "student_id": "d4f53e78-1012-5322-a4f3-4bca2efc51be",
        "score": "2",
        "submitted_at": "2024-01-01T02:00:00Z",
        "late": "gradebook_entries_late_2",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
        "id": "f56b3ad9-1edd-54ea-b539-936ceb34402a",
    },
    {
        "assignment_id": "0e5a804a-8bcd-5711-8e93-1fa2cc7bf006",
        "student_id": "d4f53e78-1012-5322-a4f3-4bca2efc51be",
        "score": "3",
        "submitted_at": "2024-01-01T03:00:00Z",
        "late": "gradebook_entries_late_3",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
        "id": "6f29cf2d-bae5-5de5-ae63-070cc18575ac",
    },
    {
        "assignment_id": "0e5a804a-8bcd-5711-8e93-1fa2cc7bf006",
        "student_id": "d4f53e78-1012-5322-a4f3-4bca2efc51be",
        "score": "4",
        "submitted_at": "2024-01-01T04:00:00Z",
        "late": "gradebook_entries_late_4",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
        "id": "782d9d82-5799-5a05-93aa-97e87d4b2c8b",
    },
    {
        "assignment_id": "0e5a804a-8bcd-5711-8e93-1fa2cc7bf006",
        "student_id": "d4f53e78-1012-5322-a4f3-4bca2efc51be",
        "score": "5",
        "submitted_at": "2024-01-01T05:00:00Z",
        "late": "gradebook_entries_late_5",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
        "id": "bdac048d-b4fb-58a9-b01c-ecbb0e2e8f66",
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
    """Seed fixed gradebook_entries rows inline (no CSV file)."""
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
