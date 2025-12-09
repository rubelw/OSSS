from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0040"
down_revision = "0039"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "pay_periods"

# Inline seed data for pay_periods
# Matches PayPeriod model + TimestampMixin:
# code, start_date, end_date, pay_date, status, id, created_at, updated_at
SEED_ROWS = [
    {
        "code": "pay_periods_code_1",
        "start_date": "2024-08-01",
        "end_date": "2024-08-14",
        "pay_date": "2024-01-02",
        "status": "pay_periods_stat",
        "id": "729d8618-d1e8-4fec-88cb-788c59c2a526",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
    },
    {
        "code": "pay_periods_code_2",
        "start_date": "2024-08-15",
        "end_date": "2024-08-28",
        "pay_date": "2024-01-03",
        "status": "pay_periods_stat",
        "id": "968e7a04-2819-4966-b6a7-9e654e9c3cfd",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
    },
    {
        "code": "pay_periods_code_3",
        "start_date": "2024-08-29",
        "end_date": "2024-09-11",
        "pay_date": "2024-01-04",
        "status": "pay_periods_stat",
        "id": "4f2beea1-4e51-4bb1-919d-86c9bb8af474",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
    },
    {
        "code": "pay_periods_code_4",
        "start_date": "2024-09-12",
        "end_date": "2024-09-25",
        "pay_date": "2024-01-05",
        "status": "pay_periods_stat",
        "id": "88a15077-478e-4eee-89cc-a06e4d89af73",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
    },
    {
        "code": "pay_periods_code_5",
        "start_date": "2024-09-26",
        "end_date": "2024-10-09",
        "pay_date": "2024-01-06",
        "status": "pay_periods_stat",
        "id": "eb0d5230-777e-417c-ae18-b3a4efe90e2d",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
    },
]


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion from inline value to appropriate DB-bound value."""
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

    # Let DB cast dates, timestamps, UUIDs, etc.
    return raw


def upgrade() -> None:
    """Load seed data for pay_periods from inline SEED_ROWS.

    Each row is inserted inside an explicit nested transaction (SAVEPOINT)
    so a failing row won't abort the whole migration transaction.
    """
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
                # let server defaults (created_at/updated_at) fill in if omitted
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
