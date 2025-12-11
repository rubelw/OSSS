from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0219"
down_revision = "0218"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "publications"
CSV_FILE = None  # using inline seed data instead of CSV

# Columns: meeting_id, published_at, public_url, is_final, created_at, updated_at, id
# Using the same meeting_id as your board meeting and realistic URLs/flags.
SEED_ROWS = [
    {
        "meeting_id": "89ab8c9b-8c20-5b36-95db-e4e7e0a5e3b4",
        "published_at": "2024-01-01T01:00:00Z",
        "public_url": "https://board.dcgschools.org/meetings/2024-01-regular/agenda-draft",
        "is_final": False,
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
        "id": "0a76d195-d4c7-593b-a9ab-e1bcbbf529a1",
    },
    {
        "meeting_id": "89ab8c9b-8c20-5b36-95db-e4e7e0a5e3b4",
        "published_at": "2024-01-01T02:00:00Z",
        "public_url": "https://board.dcgschools.org/meetings/2024-01-regular/agenda-final",
        "is_final": True,
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
        "id": "74f0ac58-9e11-5a12-8c05-442fbf7b9b2a",
    },
    {
        "meeting_id": "89ab8c9b-8c20-5b36-95db-e4e7e0a5e3b4",
        "published_at": "2024-01-01T03:00:00Z",
        "public_url": "https://board.dcgschools.org/meetings/2024-01-regular/packet",
        "is_final": True,
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
        "id": "1e5efb79-00a7-50ed-ba4e-b098a95ae88f",
    },
    {
        "meeting_id": "89ab8c9b-8c20-5b36-95db-e4e7e0a5e3b4",
        "published_at": "2024-01-01T04:00:00Z",
        "public_url": "https://board.dcgschools.org/meetings/2024-01-regular/minutes-draft",
        "is_final": False,
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
        "id": "90344f39-5767-554f-8c2e-87a2856d1c9d",
    },
    {
        "meeting_id": "89ab8c9b-8c20-5b36-95db-e4e7e0a5e3b4",
        "published_at": "2024-01-01T05:00:00Z",
        "public_url": "https://board.dcgschools.org/meetings/2024-01-regular/minutes-final",
        "is_final": True,
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
        "id": "139c2e67-32e0-57d3-b058-87c1acb7bd97",
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

    # Otherwise, pass raw through and let DB cast (UUID, timestamptz, etc.)
    return raw


def upgrade() -> None:
    """Load seed data for publications from inline SEED_ROWS (no CSV)."""
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
