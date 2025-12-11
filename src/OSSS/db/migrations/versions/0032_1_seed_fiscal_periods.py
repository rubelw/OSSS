from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0032_1"
down_revision = "0032"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "fiscal_periods"

# Inline seed data for fiscal_periods
# Columns: year_number, period_no, start_date, end_date, is_closed, id, created_at, updated_at
SEED_ROWS = [
    {
        "year_number": 1,
        "period_no": 1,
        "start_date": "2024-08-01",
        "end_date": "2024-08-30",
        "is_closed": "false",
        "id": "e03a4e59-941e-4c97-9d53-c4b72c77392e",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
    },
    {
        "year_number": 2,
        "period_no": 2,
        "start_date": "2024-08-31",
        "end_date": "2024-09-29",
        "is_closed": "true",
        "id": "66f3ac33-2758-4164-9ebc-811a2df7939b",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
    },
    {
        "year_number": 3,
        "period_no": 3,
        "start_date": "2024-09-30",
        "end_date": "2024-10-29",
        "is_closed": "false",
        "id": "535bad86-b934-4537-9dcf-3acb7df88067",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
    },
    {
        "year_number": 4,
        "period_no": 4,
        "start_date": "2024-10-30",
        "end_date": "2024-11-28",
        "is_closed": "true",
        "id": "afb076c9-5da6-4369-b238-de6d2a0a39c3",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
    },
    {
        "year_number": 5,
        "period_no": 5,
        "start_date": "2024-11-29",
        "end_date": "2024-12-28",
        "is_closed": "false",
        "id": "55f46e09-9281-4717-b688-5267185d4ed7",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
    },
]


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion from seed value to appropriate Python/DB value."""
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

    # Otherwise, pass raw through and let DB cast (ints, dates, timestamps, etc.)
    return raw


def upgrade() -> None:
    """Load seed data for fiscal_periods from inline SEED_ROWS (no CSV)."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(TABLE_NAME):
        log.warning("Table %s does not exist; skipping seed", TABLE_NAME)
        return

    if not SEED_ROWS:
        log.info("No seed rows defined for %s; skipping", TABLE_NAME)
        return

    metadata = sa.MetaData()
    table = sa.Table(TABLE_NAME, metadata, autoload_with=bind)

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

    log.info("Inserted %s inline seed rows into %s", inserted, TABLE_NAME)


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
