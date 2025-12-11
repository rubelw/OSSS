from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0130"
down_revision = "0129"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "posts"

# Inline seed data (replaces CSV)
ROWS = [
    {
        "channel_id": "76330019-00cf-5cab-954e-505b6b74d86d",
        "title": "posts_title_1",
        "body": "posts_body_1",
        "status": "posts_status_1",
        "publish_at": "2024-01-01T01:00:00Z",
        "author_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
        "id": "ec1aacab-2074-5b9f-bef5-a7dad72e0e6b",
    },
    {
        "channel_id": "76330019-00cf-5cab-954e-505b6b74d86d",
        "title": "posts_title_2",
        "body": "posts_body_2",
        "status": "posts_status_2",
        "publish_at": "2024-01-01T02:00:00Z",
        "author_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
        "id": "6638c28a-1eab-5202-b1dc-7d38fe01932c",
    },
    {
        "channel_id": "76330019-00cf-5cab-954e-505b6b74d86d",
        "title": "posts_title_3",
        "body": "posts_body_3",
        "status": "posts_status_3",
        "publish_at": "2024-01-01T03:00:00Z",
        "author_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
        "id": "f1fe96e6-10a9-5cc1-babe-597380a46ba2",
    },
    {
        "channel_id": "76330019-00cf-5cab-954e-505b6b74d86d",
        "title": "posts_title_4",
        "body": "posts_body_4",
        "status": "posts_status_4",
        "publish_at": "2024-01-01T04:00:00Z",
        "author_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
        "id": "f225eef1-7dd7-5eb4-81dc-03f9e404495a",
    },
    {
        "channel_id": "76330019-00cf-5cab-954e-505b6b74d86d",
        "title": "posts_title_5",
        "body": "posts_body_5",
        "status": "posts_status_5",
        "publish_at": "2024-01-01T05:00:00Z",
        "author_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
        "id": "d2d0c580-e980-5f87-a27e-51fdc76031a6",
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
    """Seed fixed posts rows inline (no CSV file)."""
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

    log.info("Inserted %s inline rows into %s", inserted, TABLE_NAME)


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
