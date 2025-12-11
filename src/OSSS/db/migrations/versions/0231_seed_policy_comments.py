from __future__ import annotations

import csv  # kept for consistency with other migrations, even if unused
import logging
import os

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0231"
down_revision = "0230"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "policy_comments"
CSV_FILE = None  # using inline seed data instead of CSV


# Inline seed rows with realistic values
# Columns: policy_version_id, user_id, text, visibility, id, created_at, updated_at
SEED_ROWS = [
    {
        "policy_version_id": "220ea1db-70a4-506f-8039-ffe4637cea69",
        "user_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "text": "Clarified language around parent notification timelines. Looks good overall.",
        "visibility": "internal",
        "id": "a2151faf-1899-512c-8aa6-956086f0f1f4",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
    },
    {
        "policy_version_id": "220ea1db-70a4-506f-8039-ffe4637cea69",
        "user_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "text": "Please verify that the referenced state code is the most recent revision.",
        "visibility": "internal",
        "id": "a2240190-4d04-5e5c-ab40-be6e6096d634",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
    },
    {
        "policy_version_id": "220ea1db-70a4-506f-8039-ffe4637cea69",
        "user_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "text": "Recommend adding an example scenario to help building principals apply this policy.",
        "visibility": "internal",
        "id": "167788f5-8120-5413-9b3b-6ed92e976eaf",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
    },
    {
        "policy_version_id": "220ea1db-70a4-506f-8039-ffe4637cea69",
        "user_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "text": "Legal counsel has reviewed the draft and did not identify any conflicts.",
        "visibility": "internal",
        "id": "786e6407-cea6-5b92-8393-a85379390442",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
    },
    {
        "policy_version_id": "220ea1db-70a4-506f-8039-ffe4637cea69",
        "user_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "text": "Ready for board first reading. No additional edits requested.",
        "visibility": "internal",
        "id": "276a91d9-a058-5c8a-9615-a412bf2e0505",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
    },
]


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion from seed values to appropriate Python/DB types."""
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

    # Otherwise, pass raw through and let DB cast (UUID, timestamps, etc.)
    return raw


def upgrade() -> None:
    """Load seed data for policy_comments from inline SEED_ROWS (no CSV)."""
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
