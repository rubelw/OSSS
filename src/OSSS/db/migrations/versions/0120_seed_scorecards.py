from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0120"
down_revision = "0119"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "scorecards"

# Inline seed data derived from the provided CSV
ROWS = [
    {
        "plan_id": "7f2eb6b4-2c3e-4c78-9d7a-90bb2b67e21d",
        "name": "scorecards_name_1",
        "id": "3572579a-8bff-597f-a766-59bc9bb43d93",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
    },
    {
        "plan_id": "7f2eb6b4-2c3e-4c78-9d7a-90bb2b67e21d",
        "name": "scorecards_name_2",
        "id": "0609ffbd-6e60-5266-acce-d308f40efe60",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
    },
    {
        "plan_id": "7f2eb6b4-2c3e-4c78-9d7a-90bb2b67e21d",
        "name": "scorecards_name_3",
        "id": "ea0ce482-e00f-56ce-9383-24c7d573374f",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
    },
    {
        "plan_id": "7f2eb6b4-2c3e-4c78-9d7a-90bb2b67e21d",
        "name": "scorecards_name_4",
        "id": "ea2f9cd1-570f-5bc3-b472-65f6b4b9fdf5",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
    },
    {
        "plan_id": "7f2eb6b4-2c3e-4c78-9d7a-90bb2b67e21d",
        "name": "scorecards_name_5",
        "id": "ceea6cb2-9b70-5763-82c6-37ebe6a747a5",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
    },
]


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion from inline values to appropriate Python/DB values."""
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

    # Let the DB handle casting for GUID, timestamptz, etc.
    return raw


def upgrade() -> None:
    """Seed fixed scorecard rows inline.

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

    inserted = 0
    for raw_row in ROWS:
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

    log.info("Inserted %s rows into %s (inline seed)", inserted, TABLE_NAME)


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
