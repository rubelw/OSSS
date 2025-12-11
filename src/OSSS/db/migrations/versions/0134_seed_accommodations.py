from __future__ import annotations

import csv  # kept for consistency with other migrations (unused here)
import logging
import os    # kept for consistency with other migrations (unused here)

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0134"
down_revision = "0133"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "accommodations"

# Inline seed data (replaces CSV)
ROWS = [
    {
        "iep_plan_id": "61f759cd-2ba8-5c11-9d52-86388834aaca",
        "applies_to": "accommodations_applies_to_1",
        "description": "accommodations_description_1",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
        "id": "11385319-ee79-5635-96c9-37c67e75b624",
    },
    {
        "iep_plan_id": "61f759cd-2ba8-5c11-9d52-86388834aaca",
        "applies_to": "accommodations_applies_to_2",
        "description": "accommodations_description_2",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
        "id": "73a562c0-c8a5-5830-9a1a-7f4319a416f9",
    },
    {
        "iep_plan_id": "61f759cd-2ba8-5c11-9d52-86388834aaca",
        "applies_to": "accommodations_applies_to_3",
        "description": "accommodations_description_3",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
        "id": "7a89912e-1b6b-5400-967a-f7eb8d8095c6",
    },
    {
        "iep_plan_id": "61f759cd-2ba8-5c11-9d52-86388834aaca",
        "applies_to": "accommodations_applies_to_4",
        "description": "accommodations_description_4",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
        "id": "4362b355-274b-51da-b953-54beb0052b5b",
    },
    {
        "iep_plan_id": "61f759cd-2ba8-5c11-9d52-86388834aaca",
        "applies_to": "accommodations_applies_to_5",
        "description": "accommodations_description_5",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
        "id": "36d8211f-d866-5d9a-952d-7d54f5fe8d47",
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
    """Seed fixed accommodations rows inline (no CSV file)."""
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
