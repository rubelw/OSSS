from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0243"
down_revision = "0242"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "comm_search_index"

# Inline seed data for communication search index.
# `ts` is stored as text here and cast by the DB to tsvector (or equivalent)
# based on the column type.
SEED_ROWS = [
    {
        "id": "ed754d79-fed2-40eb-878e-b4ba1b664c8a",
        "entity_type": "post",
        "entity_id": "2ebf0e66-7220-5e32-a36d-10f2a39f60fc",
        "ts": "School board meeting recap including key votes and public comments.",
    },
    {
        "id": "43dcee5d-a107-4661-bc93-9ddd419d589f",
        "entity_type": "post",
        "entity_id": "0932b0ab-6ee6-553a-9140-8a0dbba33a18",
        "ts": "District-wide announcement about winter weather procedures and snow day notifications.",
    },
    {
        "id": "e2d837d9-ad93-4451-b0a3-03ee3490fbbb",
        "entity_type": "post",
        "entity_id": "0c5a8dc9-ba13-5a93-8730-aabba7f7fd64",
        "ts": "Family newsletter covering upcoming events, curriculum highlights, and reminders.",
    },
    {
        "id": "aea76720-2a9a-4bbc-b700-42845276d77f",
        "entity_type": "post",
        "entity_id": "f02ae905-8e8a-528d-966b-3cc68a2d89cc",
        "ts": "Emergency alert detailing building closure and instructions for remote learning.",
    },
    {
        "id": "307072bc-b32e-4b02-84e9-bd6f000b5f54",
        "entity_type": "post",
        "entity_id": "a99d8288-81be-533d-836d-a7cc5eef9001",
        "ts": "Community engagement post inviting feedback on the district strategic plan.",
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

    # Let the DB handle casting for UUIDs, tsvector, etc.
    return raw


def upgrade() -> None:
    """Insert inline seed data for comm_search_index."""
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
