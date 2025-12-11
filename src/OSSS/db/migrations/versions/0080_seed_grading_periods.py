from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0080"
down_revision = "0079"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "grading_periods"

# Inline seed data
SEED_ROWS = [
    {
        "term_id": "7a51ebae-0f9a-525d-b1fa-ac15ed0b1a1f",
        "name": "Quarter 1",
        "start_date": "2024-08-23",
        "end_date": "2024-10-18",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
        "id": "1c7f96a7-5faa-5492-a149-07298173122e",
    },
    {
        "term_id": "7a51ebae-0f9a-525d-b1fa-ac15ed0b1a1f",
        "name": "Quarter 2",
        "start_date": "2024-10-21",
        "end_date": "2024-12-20",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
        "id": "a9f33565-8d04-5dc1-a354-a8014c9f651b",
    },
    {
        "term_id": "7a51ebae-0f9a-525d-b1fa-ac15ed0b1a1f",
        "name": "Quarter 3",
        "start_date": "2025-01-06",
        "end_date": "2025-03-14",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
        "id": "8c2885b1-75a9-5d0b-832d-6ebc0fbef6f7",
    },
    {
        "term_id": "7a51ebae-0f9a-525d-b1fa-ac15ed0b1a1f",
        "name": "Quarter 4",
        "start_date": "2025-03-17",
        "end_date": "2025-05-23",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
        "id": "59a26007-d0c1-513f-8443-d0a937274e16",
    },
    {
        "term_id": "7a51ebae-0f9a-525d-b1fa-ac15ed0b1a1f",
        "name": "Full Year",
        "start_date": "2024-08-23",
        "end_date": "2025-05-23",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
        "id": "089a6bbe-b4b4-5cba-935c-7cb29cede972",
    },
]


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion from inline Python values to appropriate DB values."""
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

    # Otherwise, pass raw through and let DB cast (for UUID, DATE, TIMESTAMPTZ, etc.)
    return raw


def upgrade() -> None:
    """Load seed data for grading_periods from inline SEED_ROWS.

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

    if not SEED_ROWS:
        log.info("No inline seed rows defined for %s", TABLE_NAME)
        return

    inserted = 0
    for raw_row in SEED_ROWS:
        row: dict[str, object] = {}

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
                "Skipping inline row for %s due to error: %s. Row: %s",
                TABLE_NAME,
                exc,
                raw_row,
            )

    log.info("Inserted %s inline rows into %s", inserted, TABLE_NAME)


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
