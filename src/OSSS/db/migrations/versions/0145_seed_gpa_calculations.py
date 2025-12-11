from __future__ import annotations

import csv  # kept for consistency with other migrations (unused now)
import logging
import os   # kept for consistency with other migrations (unused now)

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0145"
down_revision = "0144"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "gpa_calculations"
CSV_FILE = os.path.join(os.path.dirname(__file__), "csv", f"{TABLE_NAME}.csv")  # unused now

# Inline seed data (replaces CSV file)
ROWS = [
    {
        "student_id": "d4f53e78-1012-5322-a4f3-4bca2efc51be",
        "term_id": "7a51ebae-0f9a-525d-b1fa-ac15ed0b1a1f",
        "gpa": "1",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
        "id": "f3789f17-533b-589b-b4ed-c768dee3ca23",
    },
    {
        "student_id": "d4f53e78-1012-5322-a4f3-4bca2efc51be",
        "term_id": "7a51ebae-0f9a-525d-b1fa-ac15ed0b1a1f",
        "gpa": "2",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
        "id": "b6b1520b-a6a7-5629-936b-5ef4c6bbbef3",
    },
    {
        "student_id": "d4f53e78-1012-5322-a4f3-4bca2efc51be",
        "term_id": "7a51ebae-0f9a-525d-b1fa-ac15ed0b1a1f",
        "gpa": "3",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
        "id": "6142130b-757c-5b32-b974-dc3cf435ca50",
    },
    {
        "student_id": "d4f53e78-1012-5322-a4f3-4bca2efc51be",
        "term_id": "7a51ebae-0f9a-525d-b1fa-ac15ed0b1a1f",
        "gpa": "4",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
        "id": "dd8760f2-a79d-5548-92e2-da6cff076bad",
    },
    {
        "student_id": "d4f53e78-1012-5322-a4f3-4bca2efc51be",
        "term_id": "7a51ebae-0f9a-525d-b1fa-ac15ed0b1a1f",
        "gpa": "5",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
        "id": "e21700c5-7409-5a2b-b1a7-f9cdfa5e62c8",
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
    """Seed fixed gpa_calculations rows inline (no CSV file)."""
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

        # Explicit nested transaction (SAVEPOINT)
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
