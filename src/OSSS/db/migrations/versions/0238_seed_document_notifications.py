from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0238"
down_revision = "0237"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "document_notifications"

# Inline realistic seed data
# Scenario: a board packet document with one board member who toggles
# subscription on/off over time. This gives the UI something realistic to show
# for subscription history / audit.
#
# Columns: created_at, updated_at, id, document_id, user_id, subscribed, last_sent_at
SEED_ROWS = [
    {
        # User initially not subscribed; a one-off notification was sent.
        "id": "24290191-8ef2-5ad5-bb0f-2ed86836a305",
        "document_id": "e0c6ecb5-af4d-5c1c-bc1b-bf266b3ba7d8",  # Jan 2024 board packet
        "user_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",       # Board member / admin
        "subscribed": False,
        "last_sent_at": "2024-01-01T01:00:00Z",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
    },
    {
        # User turns on notifications; a digest was sent right away.
        "id": "17f97e8c-bdd0-5bdd-b55e-2768003305e0",
        "document_id": "e0c6ecb5-af4d-5c1c-bc1b-bf266b3ba7d8",
        "user_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "subscribed": True,
        "last_sent_at": "2024-01-01T02:00:00Z",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
    },
    {
        # User temporarily disables notifications.
        "id": "e8b1368d-d156-52f7-8d10-4b3c4178fdd3",
        "document_id": "e0c6ecb5-af4d-5c1c-bc1b-bf266b3ba7d8",
        "user_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "subscribed": False,
        "last_sent_at": "2024-01-01T03:00:00Z",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
    },
    {
        # User re-enables notifications later that morning.
        "id": "09d571b1-d268-5091-8d40-ad80dbe9ad91",
        "document_id": "e0c6ecb5-af4d-5c1c-bc1b-bf266b3ba7d8",
        "user_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "subscribed": True,
        "last_sent_at": "2024-01-01T04:00:00Z",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
    },
    {
        # Final state: unsubscribed again; last notification already sent.
        "id": "c2854581-dab0-5aa4-b077-f9f207d4270e",
        "document_id": "e0c6ecb5-af4d-5c1c-bc1b-bf266b3ba7d8",
        "user_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "subscribed": False,
        "last_sent_at": "2024-01-01T05:00:00Z",
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
            log.warning("Invalid boolean for %s.%s: %r; using NULL", TABLE_NAME, col.name, raw)
            return None
        return bool(raw)

    # Let DB handle UUID, JSONB, timestamptz, etc.
    return raw


def upgrade() -> None:
    """Insert inline seed rows into document_notifications."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(TABLE_NAME):
        log.warning("Table %s does not exist; skipping seed", TABLE_NAME)
        return

    metadata = sa.MetaData()
    table = sa.Table(TABLE_NAME, metadata, autoload_with=bind)

    inserted = 0

    for raw_row in SEED_ROWS:
        row = {}
        for col in table.columns:
            if col.name not in raw_row:
                continue
            row[col.name] = _coerce_value(col, raw_row[col.name])

        if not row:
            continue

        # Explicit nested transaction (SAVEPOINT) for row-level robustness
        nested = bind.begin_nested()
        try:
            bind.execute(table.insert().values(**row))
            nested.commit()
            inserted += 1
        except (IntegrityError, DataError, StatementError) as exc:
            nested.rollback()
            log.warning(
                "Skipping row for %s due to error: %s | Row: %s",
                TABLE_NAME,
                exc,
                raw_row,
            )

    log.info("Inserted %s inline rows into %s", inserted, TABLE_NAME)


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
