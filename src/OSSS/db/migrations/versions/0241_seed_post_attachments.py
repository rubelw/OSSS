from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0241"
down_revision = "0240"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "post_attachments"

# Inline seed rows:
# Attach several files to a single announcement / post.
SEED_ROWS = [
    {
        "id": "37a5a8a5-a02f-5683-a3a1-9776a24afe20",
        "post_id": "ec1aacab-2074-5b9f-bef5-a7dad72e0e6b",
        "file_id": "39ca63db-2221-5408-ad28-c6dfaac3056d",
    },
    {
        "id": "a1302b1a-7976-5319-83fe-cb41ffb78dcc",
        "post_id": "ec1aacab-2074-5b9f-bef5-a7dad72e0e6b",
        "file_id": "39ca63db-2221-5408-ad28-c6dfaac3056d",
    },
    {
        "id": "999397a2-0dd5-51e6-bdff-0e0fd8d6e770",
        "post_id": "ec1aacab-2074-5b9f-bef5-a7dad72e0e6b",
        "file_id": "39ca63db-2221-5408-ad28-c6dfaac3056d",
    },
    {
        "id": "5d4a0e1d-7029-551f-acc3-eb9e91b85f1d",
        "post_id": "ec1aacab-2074-5b9f-bef5-a7dad72e0e6b",
        "file_id": "39ca63db-2221-5408-ad28-c6dfaac3056d",
    },
    {
        "id": "7d25c52e-1777-5da0-aa86-9d5617f82056",
        "post_id": "ec1aacab-2074-5b9f-bef5-a7dad72e0e6b",
        "file_id": "39ca63db-2221-5408-ad28-c6dfaac3056d",
    },
]


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion from inline seed value to appropriate Python/DB value."""
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

    # Let the DB handle casting for UUIDs, etc.
    return raw


def upgrade() -> None:
    """Insert inline seed data for post_attachments."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(TABLE_NAME):
        log.warning("Table %s does not exist; skipping seed", TABLE_NAME)
        return

    metadata = sa.MetaData()
    table = sa.Table(TABLE_NAME, metadata, autoload_with=bind)

    if not SEED_ROWS:
        log.info("No inline seed rows defined for %s; skipping", TABLE_NAME)
        return

    inserted = 0

    for raw_row in SEED_ROWS:
        row = {}

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

    log.info("Inserted %s inline rows into %s", inserted, TABLE_NAME)


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
