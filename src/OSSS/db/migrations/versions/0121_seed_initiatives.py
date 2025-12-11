from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0121"
down_revision = "0120"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "initiatives"

# Inline seed data derived from the provided CSV
ROWS = [
    {
        "objective_id": "8fdb9139-143b-5726-9c7f-a9d0cd10758f",
        "name": "initiatives_name_1",
        "description": "initiatives_description_1",
        "owner_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "due_date": "2024-01-02",
        "status": "initiatives_status_1",
        "priority": "initiatives_prio",
        "id": "db1f2941-2607-519d-8636-092f41f0dc97",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
    },
    {
        "objective_id": "8fdb9139-143b-5726-9c7f-a9d0cd10758f",
        "name": "initiatives_name_2",
        "description": "initiatives_description_2",
        "owner_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "due_date": "2024-01-03",
        "status": "initiatives_status_2",
        "priority": "initiatives_prio",
        "id": "4c891793-1515-5455-b75c-3fc261c12af8",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
    },
    {
        "objective_id": "8fdb9139-143b-5726-9c7f-a9d0cd10758f",
        "name": "initiatives_name_3",
        "description": "initiatives_description_3",
        "owner_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "due_date": "2024-01-04",
        "status": "initiatives_status_3",
        "priority": "initiatives_prio",
        "id": "b96b0c4b-094c-5895-8a02-857acae843b2",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
    },
    {
        "objective_id": "8fdb9139-143b-5726-9c7f-a9d0cd10758f",
        "name": "initiatives_name_4",
        "description": "initiatives_description_4",
        "owner_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "due_date": "2024-01-05",
        "status": "initiatives_status_4",
        "priority": "initiatives_prio",
        "id": "6d47d5f3-c12c-56c9-bd92-5a036747ae32",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
    },
    {
        "objective_id": "8fdb9139-143b-5726-9c7f-a9d0cd10758f",
        "name": "initiatives_name_5",
        "description": "initiatives_description_5",
        "owner_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "due_date": "2024-01-06",
        "status": "initiatives_status_5",
        "priority": "initiatives_prio",
        "id": "b09e76b8-9ed0-5d67-a8f2-f87b65fc3123",
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

    # Let the DB handle casting for GUID, dates, timestamptz, etc.
    return raw


def upgrade() -> None:
    """Seed fixed initiative rows inline.

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
