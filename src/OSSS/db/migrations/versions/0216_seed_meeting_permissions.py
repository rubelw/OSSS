from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0216"
down_revision = "0215"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "meeting_permissions"
CSV_FILE = None  # seeding inline instead of from CSV

# Inline seed rows with realistic values
# Columns: meeting_id, user_id, can_view, can_edit, can_manage, created_at, updated_at, id
SEED_ROWS = [
    {
        # Superintendent / board secretary with full control
        "meeting_id": "89ab8c9b-8c20-5b36-95db-e4e7e0a5e3b4",
        "user_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "can_view": True,
        "can_edit": True,
        "can_manage": True,
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
        "id": "ade58094-13d9-5c04-b8ea-49dc811cf9cd",
    },
    {
        # Same user retained full access later in the day
        "meeting_id": "89ab8c9b-8c20-5b36-95db-e4e7e0a5e3b4",
        "user_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "can_view": True,
        "can_edit": True,
        "can_manage": True,
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
        "id": "94efbbc2-78f2-57ad-808f-b72ef1ed9c75",
    },
    {
        # Historical record where user had edit but not manage rights
        "meeting_id": "89ab8c9b-8c20-5b36-95db-e4e7e0a5e3b4",
        "user_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "can_view": True,
        "can_edit": True,
        "can_manage": False,
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
        "id": "6078bfc3-0543-5098-bee8-9ff98a1659ad",
    },
    {
        # View-only example permission
        "meeting_id": "89ab8c9b-8c20-5b36-95db-e4e7e0a5e3b4",
        "user_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "can_view": True,
        "can_edit": False,
        "can_manage": False,
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
        "id": "360fd3c4-7904-504d-8748-ce524184c10c",
    },
    {
        # Another view-only record (e.g., later audit change)
        "meeting_id": "89ab8c9b-8c20-5b36-95db-e4e7e0a5e3b4",
        "user_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "can_view": True,
        "can_edit": False,
        "can_manage": False,
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
        "id": "e82c6a01-b346-5062-b932-a130922f9838",
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
            log.warning("Invalid boolean for %s.%s: %r; using NULL", TABLE_NAME, col.name, raw)
            return None
        return bool(raw)

    # Otherwise, pass raw through and let DB cast (UUID, timestamptz, etc.)
    return raw


def upgrade() -> None:
    """Load seed data for meeting_permissions from inline SEED_ROWS.

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

    rows = SEED_ROWS
    if not rows:
        log.info("No inline seed rows defined for %s", TABLE_NAME)
        return

    inserted = 0
    for raw_row in rows:
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

    log.info("Inserted %s inline seed rows into %s", inserted, TABLE_NAME)


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
