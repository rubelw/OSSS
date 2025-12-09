from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0043"
down_revision = "0042"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "user_accounts"

# Inline seed data for user_accounts (aligned with UserAccount model)
SEED_ROWS = [
    {
        "person_id": "a09b6c88-3418-40b5-9f14-77800af409f7",
        "username": "michaelsmith",
        "password_hash": "password_hash_1",
        "is_active": "true",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
        "id": "79869e88-eb05-5023-b28e-d64582430541",
    },
    {
        "person_id": "79d591b1-3536-4493-a88a-8dfd0b481ead",
        "username": "sarahjohnson",
        "password_hash": "password_hash_2",
        "is_active": "true",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
        "id": "0396f19e-6c9f-56ef-93b1-3934b012e265",
    },
    {
        "person_id": "c473361d-aa2e-4ad0-bd0d-fcb73e3c780b",
        "username": "jameswilliams",
        "password_hash": "password_hash_3",
        "is_active": "true",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
        "id": "5cd2390e-4c46-57b2-99d2-618d2e529f6b",
    },
    {
        "person_id": "4d7d56ba-8041-4154-b626-6672ca04e989",
        "username": "emilybrown",
        "password_hash": "password_hash_4",
        "is_active": "true",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
        "id": "2aaa1114-7af4-5002-98a0-4153851825ea",
    },
    {
        "person_id": "2a0942e2-d035-4406-ba6b-fa61ba1f19d8",
        "username": "davidjones",
        "password_hash": "password_hash_5",
        "is_active": "true",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
        "id": "b6b64171-3b01-5426-bd1d-0d5f92dda002",
    },
]


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion from inline value to appropriate DB-bound value."""
    if raw == "" or raw is None:
        return None

    t = col.type

    # Boolean handling
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

    # Let DB cast strings for timestamps, UUIDs, etc.
    return raw


def upgrade() -> None:
    """Load seed data for user_accounts from inline SEED_ROWS.

    Each row is inserted inside an explicit nested transaction (SAVEPOINT)
    so a failing row won't abort the whole migration transaction.
    """
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(TABLE_NAME):
        log.warning("Table %s does not exist; skipping seed", TABLE_NAME)
        return

    if not SEED_ROWS:
        log.info("No seed rows defined for %s; skipping", TABLE_NAME)
        return

    metadata = sa.MetaData()
    table = sa.Table(TABLE_NAME, metadata, autoload_with=bind)

    inserted = 0
    for raw_row in SEED_ROWS:
        row: dict[str, object] = {}

        for col in table.columns:
            if col.name not in raw_row:
                # Let created_at/updated_at server defaults fill if not provided
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

    log.info("Inserted %s rows into %s from inline seed data", inserted, TABLE_NAME)


def downgrade() -> None:
    """Best-effort removal of the seeded user_accounts rows (by known IDs)."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(TABLE_NAME):
        log.warning("Table %s does not exist; skipping delete", TABLE_NAME)
        return

    metadata = sa.MetaData()
    table = sa.Table(TABLE_NAME, metadata, autoload_with=bind)

    ids = [row["id"] for row in SEED_ROWS if row.get("id")]
    if not ids:
        log.info("No IDs in SEED_ROWS; nothing to delete for %s", TABLE_NAME)
        return

    bind.execute(table.delete().where(table.c.id.in_(ids)))
    log.info("Deleted %s seeded rows from %s", len(ids), TABLE_NAME)
