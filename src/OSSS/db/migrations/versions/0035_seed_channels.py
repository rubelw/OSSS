from __future__ import annotations

import logging
import os

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0035"
down_revision = "0034_3"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "channels"

# Inline seed rows with realistic values
# Columns: org_id, name, audience, description, id, created_at, updated_at
SEED_ROWS = [
    {
        "org_id": "c201e5e9-60c0-466f-8f63-aecbf868c420",
        "name": "District-wide Announcements",
        "audience": "all",
        "description": "Primary channel for district-wide updates, closures, and time-sensitive announcements.",
        "id": "76330019-00cf-5cab-954e-505b6b74d86d",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
    },
    {
        "org_id": "c201e5e9-60c0-466f-8f63-aecbf868c420",
        "name": "Elementary Families",
        "audience": "families",
        "description": "General information, reminders, and event updates for elementary school families.",
        "id": "24d2092c-7117-550d-b880-8a17415bb108",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
    },
    {
        "org_id": "c201e5e9-60c0-466f-8f63-aecbf868c420",
        "name": "Middle School Families",
        "audience": "families",
        "description": "Communication channel for middle school families, schedules, and co-curricular updates.",
        "id": "960f9aa7-5339-573f-8610-1607357656b9",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
    },
    {
        "org_id": "c201e5e9-60c0-466f-8f63-aecbf868c420",
        "name": "High School Families",
        "audience": "families",
        "description": "High school-focused communication for academics, activities, and counseling updates.",
        "id": "312f7391-8533-52f8-9094-d7d2170347db",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
    },
    {
        "org_id": "c201e5e9-60c0-466f-8f63-aecbf868c420",
        "name": "Staff Updates",
        "audience": "staff",
        "description": "Internal channel for staff memos, HR updates, and professional learning information.",
        "id": "2a3fb81f-5ad7-55e8-b2e7-5da071d1b974",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
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

    # Otherwise, pass raw through and let DB cast (UUID, timestamptz, etc.)
    return raw


def upgrade() -> None:
    """Load seed data for channels from inline SEED_ROWS.

    Each row is inserted inside an explicit nested transaction (SAVEPOINT)
    so a failing row won't abort the whole migration transaction.
    """
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(TABLE_NAME):
        log.warning("Table %s does not exist; skipping seed", TABLE_NAME)
        return

    if not SEED_ROWS:
        log.info("No inline seed rows defined for %s; nothing to insert", TABLE_NAME)
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
