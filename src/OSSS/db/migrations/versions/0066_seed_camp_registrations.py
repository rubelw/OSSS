from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0066"
down_revision = "0065"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "camp_registrations"

# Inline seed data for camp_registrations
SEED_ROWS = [
    {
        "participant_name": "Emma Carlson",
        "camp_id": "241b464c-bfbb-5dbe-a324-0659ae6f6925",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "id": "9b8afa07-a81e-57d4-bb0f-46bca3ec7ceb",
    },
    {
        "participant_name": "Jacob Miller",
        "camp_id": "40a60e7d-3904-5c07-be2f-b8cc955d8a60",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
        "school_id": "119caaef-ef97-5364-b179-388e108bd40d",
        "id": "e867cd21-d6d6-5c07-a7cf-81414c51c9a7",
    },
    {
        "participant_name": "Ava Thompson",
        "camp_id": "17d8da20-62f1-56ae-abd2-3345e8dd57de",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
        "school_id": "b122fcb4-2864-593c-9b05-2188ef296db4",
        "id": "2f6de874-e65c-59e5-9abe-6452fc920729",
    },
    {
        "participant_name": "Liam Rodriguez",
        "camp_id": "a9b51d45-85a0-59f6-89d6-9d9c95d712f7",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
        "school_id": "df4b1423-d755-5c7f-a0ba-6908de77f61b",
        "id": "4bee2736-3cec-5c16-a2d7-71360390ab8a",
    },
    {
        "participant_name": "Olivia Jensen",
        "camp_id": "9198ffeb-b0f2-5fa7-8713-56bc8d17813d",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
        "school_id": "634b8058-d620-5a5c-86b5-c0794d3a3b73",
        "id": "2621e75a-925b-53b9-8b42-a9471c055d77",
    },
]


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion from Python-style value to appropriate DB-bound value."""
    if raw == "" or raw is None:
        return None

    t = col.type

    # Boolean handling (kept for consistency even if not used here)
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

    # Let DB/SQLAlchemy handle casting for UUID, timestamptz, etc.
    return raw


def upgrade() -> None:
    """Load seed data for camp_registrations from inline SEED_ROWS.

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

    if not SEED_ROWS:
        log.info("No seed rows defined for %s", TABLE_NAME)
        return

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

    log.info("Inserted %s rows into %s from inline SEED_ROWS", inserted, TABLE_NAME)


def downgrade() -> None:
    """Best-effort removal of the seeded camp_registrations rows."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(TABLE_NAME):
        log.warning("Table %s does not exist; skipping delete", TABLE_NAME)
        return

    if not SEED_ROWS:
        log.info("No seed rows defined for %s; nothing to delete", TABLE_NAME)
        return

    metadata = sa.MetaData()
    table = sa.Table(TABLE_NAME, metadata, autoload_with=bind)

    ids = [row["id"] for row in SEED_ROWS if "id" in row]
    if not ids:
        log.info("No IDs found in seed rows for %s; nothing to delete", TABLE_NAME)
        return

    bind.execute(table.delete().where(table.c.id.in_(ids)))
    log.info("Deleted %s seeded rows from %s", len(ids), TABLE_NAME)
