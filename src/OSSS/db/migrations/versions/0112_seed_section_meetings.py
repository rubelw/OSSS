from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0112"
down_revision = "0111"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "section_meetings"

# Inline seed data
ROWS = [
    {
        "section_id": "6e9f574f-c3ac-505d-baee-e525351b2788",
        "day_of_week": "1",
        "period_id": "23702c6c-0cb9-5fd1-9bb2-afe31b03ed78",
        "room_id": "fb53bee7-1426-5dab-b37b-b0964de845f5",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
        "id": "00956f01-9289-53f6-bf82-5bfdc67ead94",
    },
    {
        "section_id": "6e9f574f-c3ac-505d-baee-e525351b2788",
        "day_of_week": "2",
        "period_id": "23702c6c-0cb9-5fd1-9bb2-afe31b03ed78",
        "room_id": "fb53bee7-1426-5dab-b37b-b0964de845f5",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
        "id": "c5f26c57-02e8-5005-a4cb-ca050f0794d5",
    },
    {
        "section_id": "6e9f574f-c3ac-505d-baee-e525351b2788",
        "day_of_week": "3",
        "period_id": "23702c6c-0cb9-5fd1-9bb2-afe31b03ed78",
        "room_id": "fb53bee7-1426-5dab-b37b-b0964de845f5",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
        "id": "f3212604-bb62-5465-8401-7eb5732c6c6e",
    },
    {
        "section_id": "6e9f574f-c3ac-505d-baee-e525351b2788",
        "day_of_week": "4",
        "period_id": "23702c6c-0cb9-5fd1-9bb2-afe31b03ed78",
        "room_id": "fb53bee7-1426-5dab-b37b-b0964de845f5",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
        "id": "cfae69f5-cacc-5ce6-9ccf-3592eabb345f",
    },
    {
        "section_id": "6e9f574f-c3ac-505d-baee-e525351b2788",
        "day_of_week": "5",
        "period_id": "23702c6c-0cb9-5fd1-9bb2-afe31b03ed78",
        "room_id": "fb53bee7-1426-5dab-b37b-b0964de845f5",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
        "id": "6177e630-13fc-53f3-8cd6-b527c083b75d",
    },
]


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion from inline value to appropriate Python/DB value."""
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

    # Otherwise, pass raw through and let DB cast (ints/dates/timestamps/UUIDs/etc)
    return raw


def upgrade() -> None:
    """Seed fixed section_meetings rows inline.

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
