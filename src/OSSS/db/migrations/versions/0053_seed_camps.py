from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0053"
down_revision = "0052"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "camps"

# Inline seed data
SEED_ROWS = [
    {
        "name": "DCG High School Summer Strength & Conditioning Camp",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "id": "241b464c-bfbb-5dbe-a324-0659ae6f6925",
    },
    {
        "name": "DCG Middle School STEM & Robotics Camp",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
        "school_id": "119caaef-ef97-5364-b179-388e108bd40d",
        "id": "40a60e7d-3904-5c07-be2f-b8cc955d8a60",
    },
    {
        "name": "South Prairie Elementary Reading & STEAM Camp",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
        "school_id": "b122fcb4-2864-593c-9b05-2188ef296db4",
        "id": "17d8da20-62f1-56ae-abd2-3345e8dd57de",
    },
    {
        "name": "Heritage Elementary Arts & Enrichment Camp",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
        "school_id": "df4b1423-d755-5c7f-a0ba-6908de77f61b",
        "id": "a9b51d45-85a0-59f6-89d6-9d9c95d712f7",
    },
    {
        "name": "North Ridge Elementary Outdoor Exploration Camp",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
        "school_id": "634b8058-d620-5a5c-86b5-c0794d3a3b73",
        "id": "9198ffeb-b0f2-5fa7-8713-56bc8d17813d",
    },
]


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion from Python/CSV-ish value to appropriate Python value."""
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

    # Otherwise, pass raw through and let DB cast (timestamps, UUIDs, etc.)
    return raw


def upgrade() -> None:
    """Inline seed data for camps table."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(TABLE_NAME):
        log.warning("Table %s does not exist; skipping seed", TABLE_NAME)
        return

    if not SEED_ROWS:
        log.info("No inline seed rows defined for %s; skipping", TABLE_NAME)
        return

    metadata = sa.MetaData()
    table = sa.Table(TABLE_NAME, metadata, autoload_with=bind)

    inserted = 0
    for raw_row in SEED_ROWS:
        row: dict[str, object] = {}

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
                "Skipping inline row for %s due to error: %s. Row: %s",
                TABLE_NAME,
                exc,
                raw_row,
            )

    log.info("Inserted %s inline rows into %s", inserted, TABLE_NAME)


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
