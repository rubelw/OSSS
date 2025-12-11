from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0129"
down_revision = "0128"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "pages"

# Inline seed data (replaces CSV)
ROWS = [
    {
        "slug": "pages_slug_1",
        "title": "pages_title_1",
        "body": "pages_body_1",
        "status": "pages_status_1",
        "published_at": "2024-01-01T01:00:00Z",
        "channel_id": "76330019-00cf-5cab-954e-505b6b74d86d",
        "id": "9baf1ff8-2f54-5bc8-ba3e-0e19a513bbd2",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
    },
    {
        "slug": "pages_slug_2",
        "title": "pages_title_2",
        "body": "pages_body_2",
        "status": "pages_status_2",
        "published_at": "2024-01-01T02:00:00Z",
        "channel_id": "76330019-00cf-5cab-954e-505b6b74d86d",
        "id": "e0123c0a-cb79-58c5-9f0c-e81123da397a",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
    },
    {
        "slug": "pages_slug_3",
        "title": "pages_title_3",
        "body": "pages_body_3",
        "status": "pages_status_3",
        "published_at": "2024-01-01T03:00:00Z",
        "channel_id": "76330019-00cf-5cab-954e-505b6b74d86d",
        "id": "4a0aa661-367b-5ce8-9f4f-dd79a01dc856",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
    },
    {
        "slug": "pages_slug_4",
        "title": "pages_title_4",
        "body": "pages_body_4",
        "status": "pages_status_4",
        "published_at": "2024-01-01T04:00:00Z",
        "channel_id": "76330019-00cf-5cab-954e-505b6b74d86d",
        "id": "c2ddb8a5-f4a1-59fa-a97f-68c6f52ff4c6",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
    },
    {
        "slug": "pages_slug_5",
        "title": "pages_title_5",
        "body": "pages_body_5",
        "status": "pages_status_5",
        "published_at": "2024-01-01T05:00:00Z",
        "channel_id": "76330019-00cf-5cab-954e-505b6b74d86d",
        "id": "47634072-5800-5c10-ac40-cc94009dac17",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
    },
]


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion from inline seed rows to appropriate Python value."""
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

    # Otherwise, let the DB cast (UUID, timestamptz, numeric, etc.)
    return raw


def upgrade() -> None:
    """Seed fixed pages rows inline (no CSV file)."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(TABLE_NAME):
        log.warning("Table %s does not exist; skipping seed", TABLE_NAME)
        return

    metadata = sa.MetaData()
    table = sa.Table(TABLE_NAME, metadata, autoload_with=bind)

    if not ROWS:
        log.info("No inline rows for %s; skipping", TABLE_NAME)
        return

    inserted = 0
    for raw_row in ROWS:
        row: dict[str, object] = {}

        for col in table.columns:
            if col.name not in raw_row:
                continue
            raw_val = raw_row[col.name]
            row[col.name] = _coerce_value(col, raw_val)

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

    log.info("Inserted %s inline rows into %s", inserted, TABLE_NAME)


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
