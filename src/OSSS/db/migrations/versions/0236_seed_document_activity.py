from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0236"
down_revision = "0235"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "document_activity"

# Inline realistic seed data
# Columns:
#   created_at, updated_at, document_id, actor_id, action, at, meta, id
#
# Scenario: a superintendent reviews and collaborates on a board agenda packet.
SEED_ROWS = [
    {
        "id": "bf1168f4-b4d5-58df-814b-b3777c9a3ebd",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
        "document_id": "e0c6ecb5-af4d-5c1c-bc1b-bf266b3ba7d8",
        "actor_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",  # Superintendent
        "action": "viewed",
        "at": "2024-01-01T01:00:00Z",
        "meta": {
            "ip": "10.0.0.5",
            "user_agent": "Chrome/120.0",
            "location": "District Office",
        },
    },
    {
        "id": "96e4624c-5f34-56c1-855f-2f3ef1f497a8",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
        "document_id": "e0c6ecb5-af4d-5c1c-bc1b-bf266b3ba7d8",
        "actor_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "action": "comment_added",
        "at": "2024-01-01T02:00:00Z",
        "meta": {
            "section": "General Business",
            "comment_summary": "Requested clarification on contract renewal language.",
        },
    },
    {
        "id": "8bd684e7-9bc7-5803-bf0e-e5d1132e1ca3",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
        "document_id": "e0c6ecb5-af4d-5c1c-bc1b-bf266b3ba7d8",
        "actor_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "action": "edited_title",
        "at": "2024-01-01T03:00:00Z",
        "meta": {
            "previous_title": "January Board Packet",
            "new_title": "January 2024 Board Meeting Packet",
        },
    },
    {
        "id": "2a024336-cf75-519d-b209-fc7c7429df4a",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
        "document_id": "e0c6ecb5-af4d-5c1c-bc1b-bf266b3ba7d8",
        "actor_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "action": "uploaded_new_version",
        "at": "2024-01-01T04:00:00Z",
        "meta": {
            "version": 2,
            "file_name": "board_packet_jan_2024_v2.pdf",
            "change_note": "Updated staffing report and financial summary.",
        },
    },
    {
        "id": "81a6117c-e2e3-5fe2-9504-9558199a2bc3",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
        "document_id": "e0c6ecb5-af4d-5c1c-bc1b-bf266b3ba7d8",
        "actor_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "action": "shared_link",
        "at": "2024-01-01T05:00:00Z",
        "meta": {
            "shared_with_role": "Board Members",
            "shared_via": "email",
            "message_preview": "Please review the January board packet before Friday’s meeting.",
        },
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

    # Let DB handle UUID, JSONB, timestamptz, etc.
    return raw


def upgrade() -> None:
    """Insert inline seed rows into document_activity."""
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
