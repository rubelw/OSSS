from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0113"
down_revision = "0112"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "section_room_assignments"

# Inline seed data
ROWS = [
    {
        "section_id": "6e9f574f-c3ac-505d-baee-e525351b2788",
        "room_id": "fb53bee7-1426-5dab-b37b-b0964de845f5",
        "start_date": "2024-01-02",
        "end_date": "2024-01-02",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
        "id": "f448927f-f4a8-5aa6-b64c-0b0590677ed8",
    },
    {
        "section_id": "6e9f574f-c3ac-505d-baee-e525351b2788",
        "room_id": "fb53bee7-1426-5dab-b37b-b0964de845f5",
        "start_date": "2024-01-03",
        "end_date": "2024-01-03",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
        "id": "1c912609-10aa-5a13-8365-d01c2c5664ed",
    },
    {
        "section_id": "6e9f574f-c3ac-505d-baee-e525351b2788",
        "room_id": "fb53bee7-1426-5dab-b37b-b0964de845f5",
        "start_date": "2024-01-04",
        "end_date": "2024-01-04",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
        "id": "c63f2fd0-3625-5ee7-b097-4ea17e7cf6ec",
    },
    {
        "section_id": "6e9f574f-c3ac-505d-baee-e525351b2788",
        "room_id": "fb53bee7-1426-5dab-b37b-b0964de845f5",
        "start_date": "2024-01-05",
        "end_date": "2024-01-05",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
        "id": "cc2e8181-0b28-57d5-aa1f-3adaec9d1dcc",
    },
    {
        "section_id": "6e9f574f-c3ac-505d-baee-e525351b2788",
        "room_id": "fb53bee7-1426-5dab-b37b-b0964de845f5",
        "start_date": "2024-01-06",
        "end_date": "2024-01-06",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
        "id": "31dd4331-a8bb-5415-9fd3-e84aa1653f9a",
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

    # Otherwise, pass raw through and let DB cast (dates, UUIDs, timestamps, etc.)
    return raw


def upgrade() -> None:
    """Seed fixed section_room_assignments rows inline.

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

    log.info("Inserted %s rows into %s (inline seed)", inserted, TABLE_NAME)


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
