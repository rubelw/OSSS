from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0063"
down_revision = "0062"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "plans"

# Inline seed data for plans
# Columns: id, org_id, name, cycle_start, cycle_end, status, created_at, updated_at
SEED_ROWS = [
    {
        "org_id": "c201e5e9-60c0-466f-8f63-aecbf868c420",
        "name": "2024–2027 Strategic Plan",
        "cycle_start": "2024-07-01",
        "cycle_end": "2027-06-30",
        "status": "active",
        "id": "7f2eb6b4-2c3e-4c78-9d7a-90bb2b67e21d",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
    },
    {
        "org_id": "c201e5e9-60c0-466f-8f63-aecbf868c420",
        "name": "Technology & Data Improvement Plan 2024–2025",
        "cycle_start": "2024-07-01",
        "cycle_end": "2025-06-30",
        "status": "active",
        "id": "a1e3a9af-d8a9-4afc-b17b-bf391b5f3b6f",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
    },
    {
        "org_id": "c201e5e9-60c0-466f-8f63-aecbf868c420",
        "name": "School Safety & Crisis Response Plan 2024",
        "cycle_start": "2024-01-01",
        "cycle_end": "2024-12-31",
        "status": "active",
        "id": "d84eb8f7-142c-48cb-8d62-7f926e70bea8",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
    },
    {
        "org_id": "c201e5e9-60c0-466f-8f63-aecbf868c420",
        "name": "Continuous School Improvement Plan (CSIP) 2023–2026",
        "cycle_start": "2023-07-01",
        "cycle_end": "2026-06-30",
        "status": "active",
        "id": "3b0cfc83-4b5c-4e21-a17b-a8b5f5532d0d",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
    },
    {
        "org_id": "c201e5e9-60c0-466f-8f63-aecbf868c420",
        "name": "Special Education Delivery Plan 2024–2027",
        "cycle_start": "2024-07-01",
        "cycle_end": "2027-06-30",
        "status": "draft",
        "id": "8c9bbd8a-1c7e-4ad5-8f93-973266047a84",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
    },
]


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion from Python/CSV-style value to appropriate DB-bound value."""
    if raw == "" or raw is None:
        return None

    t = col.type

    # Boolean handling
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

    # Let DB/SQLAlchemy handle Date / DateTime / UUID / String casting
    return raw


def upgrade() -> None:
    """Load seed data for plans from inline SEED_ROWS.

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
        log.info("No seed rows defined for %s", TABLE_NAME)
        return

    inserted = 0
    for raw_row in SEED_ROWS:
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

    log.info("Inserted %s rows into %s from inline SEED_ROWS", inserted, TABLE_NAME)


def downgrade() -> None:
    """Best-effort removal of the seeded plans rows."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(TABLE_NAME):
        log.warning("Table %s does not exist; skipping delete", TABLE_NAME)
        return

    if not SEED_ROWS:
        log.info("No seed rows defined for %s; nothing to delete", TABLE_NAME)
        return

    metadata = sa.MetaData()
    table = sa.Table(TABLE_NAME, metadata, autoload_with=bind)

    ids = [row["id"] for row in SEED_ROWS if "id" in row]
    if not ids:
        log.info("No IDs found in seed rows for %s; nothing to delete", TABLE_NAME)
        return

    bind.execute(table.delete().where(table.c.id.in_(ids)))
    log.info("Deleted %s seeded rows from %s", len(ids), TABLE_NAME)
