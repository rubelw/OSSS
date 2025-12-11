from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0202"
down_revision = "0201"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "fan_app_settings"

# Inline seed rows with realistic fan app configuration
# Columns: key, value, created_at, updated_at, school_id, settings, id
SEED_ROWS = [
    {
        "key": "primary_theme_color",
        "value": "#004B8D",  # school brand blue
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "settings": {
            "description": "Primary brand color for the fan app UI.",
            "category": "appearance",
            "preview_text": "Used for headers, buttons, and highlights.",
        },
        "id": "5b052128-2ac8-5f73-a732-87e2ad6d9d47",
    },
    {
        "key": "show_live_scores",
        "value": "true",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "settings": {
            "description": "Controls whether fans see live scoring updates.",
            "type": "boolean",
            "default": True,
        },
        "id": "32b333b6-01d0-5e91-a557-d09820aeb6d3",
    },
    {
        "key": "ticket_portal_url",
        "value": "https://tickets.examplehs.edu",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "settings": {
            "description": "Public URL where fans can purchase digital tickets.",
            "category": "links",
            "open_in_webview": True,
        },
        "id": "28a7dfa8-a1e7-5d05-aedf-18afce9b6812",
    },
    {
        "key": "concessions_enabled",
        "value": "true",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "settings": {
            "description": "Enable mobile ordering for concessions in the fan app.",
            "type": "boolean",
            "default": False,
        },
        "id": "6e48d6f4-d1d8-53ba-aa42-e5548e5f10a0",
    },
    {
        "key": "fan_code_of_conduct_url",
        "value": "https://examplehs.edu/athletics/fan-code-of-conduct",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "settings": {
            "description": "Link shown in the app menu for fan expectations and conduct.",
            "category": "policy",
            "requires_acknowledgement": True,
        },
        "id": "b7fd0b35-ea42-54ee-ba19-f873cb666095",
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

    # Otherwise, pass raw through and let DB cast (JSONB, UUID, timestamptz, etc.)
    return raw


def upgrade() -> None:
    """Load seed data for fan_app_settings from inline SEED_ROWS.

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

    log.info("Inserted %s inline seed rows into %s", inserted, TABLE_NAME)


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
