from __future__ import annotations

import csv  # kept for consistency with other migrations (unused here)
import logging
import os    # kept for consistency with other migrations (unused here)

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0133"
down_revision = "0132"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "iep_plans"

# Inline seed data (replaces CSV)
ROWS = [
    {
        "special_ed_case_id": "a9b4b679-1daa-58d9-93b4-54f8e4a1c698",
        "effective_start": "2024-01-02",
        "effective_end": "2024-01-02",
        "summary": "iep_plans_summary_1",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
        "id": "61f759cd-2ba8-5c11-9d52-86388834aaca",
    },
    {
        "special_ed_case_id": "a9b4b679-1daa-58d9-93b4-54f8e4a1c698",
        "effective_start": "2024-01-03",
        "effective_end": "2024-01-03",
        "summary": "iep_plans_summary_2",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
        "id": "6fb9307c-2c93-5073-a28d-93be4c4a4abe",
    },
    {
        "special_ed_case_id": "a9b4b679-1daa-58d9-93b4-54f8e4a1c698",
        "effective_start": "2024-01-04",
        "effective_end": "2024-01-04",
        "summary": "iep_plans_summary_3",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
        "id": "e30c9bef-75d7-5af8-95ab-dd0a2048eae7",
    },
    {
        "special_ed_case_id": "a9b4b679-1daa-58d9-93b4-54f8e4a1c698",
        "effective_start": "2024-01-05",
        "effective_end": "2024-01-05",
        "summary": "iep_plans_summary_4",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
        "id": "c385afd6-cf5e-53d8-baa1-50868318f894",
    },
    {
        "special_ed_case_id": "a9b4b679-1daa-58d9-93b4-54f8e4a1c698",
        "effective_start": "2024-01-06",
        "effective_end": "2024-01-06",
        "summary": "iep_plans_summary_5",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
        "id": "d0756660-b0d2-5c47-b685-a34a6bb425cc",
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

    # Otherwise, pass raw through and let DB cast (UUID, dates, timestamptz, etc.)
    return raw


def upgrade() -> None:
    """Seed fixed iep_plans rows inline (no CSV file)."""
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
