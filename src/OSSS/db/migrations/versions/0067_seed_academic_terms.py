from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0067"
down_revision = "0066"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "academic_terms"

# Inline seed data for academic_terms
SEED_ROWS = [
    {
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "name": "2024–2025 School Year",
        "type": "year",
        "start_date": "2024-08-23",
        "end_date": "2025-05-30",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
        "id": "7a51ebae-0f9a-525d-b1fa-ac15ed0b1a1f",
    },
    {
        "school_id": "119caaef-ef97-5364-b179-388e108bd40d",
        "name": "2024–2025 School Year",
        "type": "year",
        "start_date": "2024-08-23",
        "end_date": "2025-05-30",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
        "id": "c68e3617-9b1f-570b-ba9a-b4ea4f337e90",
    },
    {
        "school_id": "b122fcb4-2864-593c-9b05-2188ef296db4",
        "name": "2024–2025 School Year",
        "type": "year",
        "start_date": "2024-08-23",
        "end_date": "2025-05-30",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
        "id": "31b98760-ac52-5256-af21-3b8a8a4b35b7",
    },
    {
        "school_id": "df4b1423-d755-5c7f-a0ba-6908de77f61b",
        "name": "2024–2025 School Year",
        "type": "year",
        "start_date": "2024-08-23",
        "end_date": "2025-05-30",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
        "id": "39424df9-dc4f-5bbb-824b-53dbdd1d331e",
    },
    {
        "school_id": "634b8058-d620-5a5c-86b5-c0794d3a3b73",
        "name": "2024–2025 School Year",
        "type": "year",
        "start_date": "2024-08-23",
        "end_date": "2025-05-30",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
        "id": "295da124-be4f-538d-8e00-ed6d79e6051b",
    },
]


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion from Python-style value to appropriate DB-bound value."""
    if raw == "" or raw is None:
        return None

    t = col.type

    # Boolean handling (kept for consistency)
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

    # Let DB/SQLAlchemy handle casting for other types (dates, timestamptz, UUID, etc.)
    return raw


def upgrade() -> None:
    """Load seed data for academic_terms from inline SEED_ROWS.

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
    """Best-effort removal of the seeded academic_terms rows."""
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
