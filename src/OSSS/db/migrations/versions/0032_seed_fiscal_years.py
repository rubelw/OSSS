from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0032"
down_revision = "0030"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "fiscal_years"

# Inline seed data for fiscal_years
# Columns: year, start_date, end_date, is_closed, id, created_at, updated_at
SEED_ROWS = [
    {
        "year": 1,
        "start_date": "2023-07-01",
        "end_date": "2024-06-30",
        "is_closed": False,
        "id": "428177d1-02c0-4e4d-b690-44cc399f6dd9",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
    },
    {
        "year": 2,
        "start_date": "2024-07-01",
        "end_date": "2025-06-30",
        "is_closed": True,
        "id": "164ddfea-8dbf-4762-b4d3-7f4b08485bfd",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
    },
    {
        "year": 3,
        "start_date": "2022-07-01",
        "end_date": "2023-06-30",
        "is_closed": False,
        "id": "fabbb17e-69cb-4843-92c2-44ce35688709",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
    },
    {
        "year": 4,
        "start_date": "2021-07-01",
        "end_date": "2022-06-30",
        "is_closed": True,
        "id": "2c888170-38c4-4cbd-a816-caaf006a95f7",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
    },
    {
        "year": 5,
        "start_date": "2020-07-01",
        "end_date": "2021-06-30",
        "is_closed": False,
        "id": "69525dd2-4f63-4366-b6e5-a1d4368e8217",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
    },
]


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion from seed value to appropriate DB value."""
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

    # Otherwise, pass raw through and let DB cast (dates, timestamps, etc.)
    return raw


def upgrade() -> None:
    """Load seed data for fiscal_years from inline SEED_ROWS (no CSV)."""
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
