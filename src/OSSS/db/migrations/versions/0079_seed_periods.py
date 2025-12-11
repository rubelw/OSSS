from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0079"
down_revision = "0078"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "periods"

# Inline seed data
SEED_ROWS = [
    {
        "bell_schedule_id": "f659f393-6e85-58cd-a296-bc9f766e3491",
        "name": "Period 1",
        "start_time": "08:10:00",
        "end_time": "09:30:00",
        "sequence": 1,
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
        "id": "23702c6c-0cb9-5fd1-9bb2-afe31b03ed78",
    },
    {
        "bell_schedule_id": "f659f393-6e85-58cd-a296-bc9f766e3491",
        "name": "Period 2",
        "start_time": "09:35:00",
        "end_time": "10:55:00",
        "sequence": 2,
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
        "id": "01c52eed-7b93-5342-bc8e-42fde840f219",
    },
    {
        "bell_schedule_id": "f659f393-6e85-58cd-a296-bc9f766e3491",
        "name": "Period 3",
        "start_time": "11:00:00",
        "end_time": "12:20:00",
        "sequence": 3,
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
        "id": "7ad6fbff-bf99-5e71-9d43-05e9aebac6f8",
    },
    {
        "bell_schedule_id": "f659f393-6e85-58cd-a296-bc9f766e3491",
        "name": "Period 4",
        "start_time": "12:55:00",
        "end_time": "14:15:00",
        "sequence": 4,
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
        "id": "a4d6b417-9dbf-57bf-bc04-8bf424709bb0",
    },
    {
        "bell_schedule_id": "f659f393-6e85-58cd-a296-bc9f766e3491",
        "name": "Period 5",
        "start_time": "14:20:00",
        "end_time": "15:40:00",
        "sequence": 5,
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
        "id": "c22df1ca-c02d-584d-967c-3e2474bce988",
    },
]


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion from Python/str values to appropriate DB type."""
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

    # Otherwise, pass raw through and let DB cast
    return raw


def upgrade() -> None:
    """Load seed data for periods from inline SEED_ROWS."""

    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(TABLE_NAME):
        log.warning("Table %s does not exist; skipping seed", TABLE_NAME)
        return

    metadata = sa.MetaData()
    table = sa.Table(TABLE_NAME, metadata, autoload_with=bind)

    if not SEED_ROWS:
        log.info("No SEED_ROWS defined for %s; nothing to insert", TABLE_NAME)
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
                "Skipping row for %s due to error: %s. Row: %s",
                TABLE_NAME,
                exc,
                raw_row,
            )

    log.info("Inserted %s rows into %s from inline SEED_ROWS", inserted, TABLE_NAME)


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
