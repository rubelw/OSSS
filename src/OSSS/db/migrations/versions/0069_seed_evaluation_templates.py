from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0069"
down_revision = "0067"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "evaluation_templates"

# Inline seed data for evaluation_templates
SEED_ROWS = [
    {
        "name": "Teacher Evaluation 2024",
        "for_role": "evaluation_templates_for_role_1",
        "version": 1,
        "is_active": False,
        "id": "f48b66b5-fbda-4b6f-9d40-048fdd6839de",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
    },
    {
        "name": "Principal Evaluation 2024",
        "for_role": "evaluation_templates_for_role_2",
        "version": 1,
        "is_active": True,
        "id": "a91e65c5-a77f-4e01-bdf3-d00d55c7242c",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
    },
    {
        "name": "Coach Evaluation 2024",
        "for_role": "evaluation_templates_for_role_3",
        "version": 1,
        "is_active": False,
        "id": "95cac2ee-4b0d-40e1-89c0-cca51f77e4e2",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
    },
    {
        "name": "Counselor Evaluation 2024",
        "for_role": "evaluation_templates_for_role_4",
        "version": 1,
        "is_active": True,
        "id": "e43785ae-f266-49f0-8f47-9d15d84cefe9",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
    },
    {
        "name": "Support Staff Evaluation 2024",
        "for_role": "evaluation_templates_for_role_5",
        "version": 1,
        "is_active": False,
        "id": "a9c3a0c9-cae4-45da-916b-6cf8200c2402",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
    },
]


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion from Python-style value to appropriate DB-bound value."""
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

    # Let DB/SQLAlchemy handle casting for other types (timestamps, UUIDs, etc.)
    return raw


def upgrade() -> None:
    """Load seed data for evaluation_templates from inline SEED_ROWS.

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
    """Best-effort removal of the seeded evaluation_templates rows."""
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
