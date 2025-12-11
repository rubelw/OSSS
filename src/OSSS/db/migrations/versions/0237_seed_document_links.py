from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0237"
down_revision = "0236"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "document_links"

# Inline realistic seed data
# Columns: document_id, entity_type, entity_id, created_at, updated_at, id
#
# Scenario: the January 2024 board packet document is linked to several related
# entities in the system (meeting, agenda item, policy, plan, and resolution).
SEED_ROWS = [
    {
        "id": "12ada070-7409-5493-84d2-bbc75c339261",
        "document_id": "e0c6ecb5-af4d-5c1c-bc1b-bf266b3ba7d8",
        "entity_type": "meeting",
        "entity_id": "89ab8c9b-8c20-5b36-95db-e4e7e0a5e3b4",  # January 2024 board meeting
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
    },
    {
        "id": "884d8e61-e466-5815-a465-cf892ba17994",
        "document_id": "e0c6ecb5-af4d-5c1c-bc1b-bf266b3ba7d8",
        "entity_type": "agenda_item",
        "entity_id": "ca321d07-eec1-539e-a9f4-17f7d2533683",  # Agenda item: consent calendar
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
    },
    {
        "id": "1dbcdd3a-b92a-5d79-8384-fe0b414b161f",
        "document_id": "e0c6ecb5-af4d-5c1c-bc1b-bf266b3ba7d8",
        "entity_type": "policy",
        "entity_id": "d477da15-1f3d-57d4-a0fe-634112919663",  # Policy referenced in the packet
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
    },
    {
        "id": "92efb563-b8f1-5024-83c8-d3fa55e73917",
        "document_id": "e0c6ecb5-af4d-5c1c-bc1b-bf266b3ba7d8",
        "entity_type": "plan",
        "entity_id": "58723aa5-bfc7-5dfd-8e24-43fbc2bac0bd",  # Strategic plan referenced
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
    },
    {
        "id": "56d850a9-9ab7-5327-ba6c-a69fededf731",
        "document_id": "e0c6ecb5-af4d-5c1c-bc1b-bf266b3ba7d8",
        "entity_type": "resolution",
        "entity_id": "95bc3bae-f894-55c8-acf7-e831ffe07226",  # Resolution adopted at the meeting
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

    # Let DB handle UUID, JSONB, timestamptz, etc.
    return raw


def upgrade() -> None:
    """Insert inline seed rows into document_links."""
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
