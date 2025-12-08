from __future__ import annotations

import logging
from urllib.parse import urlparse

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "embeds"

SEED_ROWS = [
    {
        "id": "982d7cd5-b195-40e0-860a-b9f92214cfb7",
        "name": "Embedded Map 1",
        "embed_type": "map",
        "url": "https://embed.example.com/map/1",
        "description": "Map embed for district portal page 1.",
    },
    {
        "id": "98772c4c-7d9a-46b5-82cc-f43daa77feeb",
        "name": "Embedded Video 2",
        "embed_type": "video",
        "url": "https://embed.example.com/video/2",
        "description": "Video embed for district portal page 2.",
    },
    {
        "id": "46dc9d22-c990-40ad-b8d9-fd45a72a3be8",
        "name": "Embedded Form 3",
        "embed_type": "form",
        "url": "https://embed.example.com/form/3",
        "description": "Form embed for district portal page 3.",
    },
    {
        "id": "91d2568a-3f2b-4392-b3d1-a036ea549de4",
        "name": "Embedded Dashboard 4",
        "embed_type": "dashboard",
        "url": "https://embed.example.com/dashboard/4",
        "description": "Dashboard embed for district portal page 4.",
    },
    {
        "id": "47e79056-7306-4e15-96da-e83d2e5d0535",
        "name": "Embedded Calendar 5",
        "embed_type": "calendar",
        "url": "https://embed.example.com/calendar/5",
        "description": "Calendar embed for district portal page 5.",
    },
]


def _derive_provider(raw_row: dict) -> str:
    """
    Derive NOT NULL `provider` column from the URL.
    Example: 'https://embed.example.com/map/1' -> 'embed.example.com'
    """
    url = (raw_row.get("url") or "").strip()
    if url:
        try:
            netloc = urlparse(url).netloc
            if netloc:
                return netloc
        except Exception:
            log.warning("Failed to parse URL for provider: %r", url)

    # Fallbacks if URL is missing or unparsable
    embed_type = raw_row.get("embed_type") or "unknown"
    return f"provider-{embed_type}"


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion from CSV-style string to appropriate Python value."""
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

    # Otherwise, pass raw through and let DB cast
    return raw


def upgrade() -> None:
    """Load seed data for embeds from inline SEED_ROWS.

    Each row is inserted inside an explicit nested transaction (SAVEPOINT)
    so a failing row won't abort the whole migration transaction.
    """
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(TABLE_NAME):
        log.warning("Table %s does not exist; skipping seed", TABLE_NAME)
        return

    if not SEED_ROWS:
        log.info("No seed rows defined for %s; skipping", TABLE_NAME)
        return

    metadata = sa.MetaData()
    table = sa.Table(TABLE_NAME, metadata, autoload_with=bind)

    inserted = 0
    for raw_row in SEED_ROWS:
        row = {}

        for col in table.columns:
            # Always populate NOT NULL `provider` even though it's not in SEED_ROWS
            if col.name == "provider":
                raw_val = _derive_provider(raw_row)
                value = _coerce_value(col, raw_val)
                row[col.name] = value
                continue

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

    log.info(
        "Inserted %s rows into %s from inline seed data",
        inserted,
        TABLE_NAME,
    )


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
