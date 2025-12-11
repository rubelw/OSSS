from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0131"
down_revision = "0130"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "deliveries"

# Inline seed data (replaces CSV)
ROWS = [
    {
        "post_id": "ec1aacab-2074-5b9f-bef5-a7dad72e0e6b",
        "user_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "delivered_at": "2024-01-01T01:00:00Z",
        "medium": "deliveries_mediu",
        "status": "deliveries_statu",
        "id": "bdc6e646-eed8-504f-9489-ffa839ff5327",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
    },
    {
        "post_id": "ec1aacab-2074-5b9f-bef5-a7dad72e0e6b",
        "user_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "delivered_at": "2024-01-01T02:00:00Z",
        "medium": "deliveries_mediu",
        "status": "deliveries_statu",
        "id": "6b423c4f-d19e-5b02-841a-8f74b4291f19",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
    },
    {
        "post_id": "ec1aacab-2074-5b9f-bef5-a7dad72e0e6b",
        "user_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "delivered_at": "2024-01-01T03:00:00Z",
        "medium": "deliveries_mediu",
        "status": "deliveries_statu",
        "id": "bc85d946-42d1-5146-9f27-2949a13a868d",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
    },
    {
        "post_id": "ec1aacab-2074-5b9f-bef5-a7dad72e0e6b",
        "user_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "delivered_at": "2024-01-01T04:00:00Z",
        "medium": "deliveries_mediu",
        "status": "deliveries_statu",
        "id": "fc1db4db-e1fb-5c10-944d-48a4f853c47f",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
    },
    {
        "post_id": "ec1aacab-2074-5b9f-bef5-a7dad72e0e6b",
        "user_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "delivered_at": "2024-01-01T05:00:00Z",
        "medium": "deliveries_mediu",
        "status": "deliveries_statu",
        "id": "318cf986-692c-527f-b748-139485b894eb",
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

    # Otherwise, let the DB cast (UUID, timestamptz, etc.)
    return raw


def upgrade() -> None:
    """Seed fixed deliveries rows inline (no CSV file)."""
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
