from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0123"
down_revision = "0122"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "ticket_types"

# Inline seed data derived from the provided CSV
ROWS = [
    {
        "name": "ticket_types_name_1",
        "price_cents": 1,
        "quantity_total": 1,
        "quantity_sold": 1,
        "sales_starts_at": "2024-01-01T01:00:00Z",
        "sales_ends_at": "2024-01-01T01:00:00Z",
        "attributes": {},
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
        "event_id": "13e28612-f86c-5753-8964-2ed13f37a8b4",
        "id": "4408eb5e-fcb7-5e86-885a-a08b5bf3015c",
    },
    {
        "name": "ticket_types_name_2",
        "price_cents": 2,
        "quantity_total": 2,
        "quantity_sold": 2,
        "sales_starts_at": "2024-01-01T02:00:00Z",
        "sales_ends_at": "2024-01-01T02:00:00Z",
        "attributes": {},
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
        "event_id": "13e28612-f86c-5753-8964-2ed13f37a8b4",
        "id": "565882ec-a9ad-5d68-b1fe-a33342369837",
    },
    {
        "name": "ticket_types_name_3",
        "price_cents": 3,
        "quantity_total": 3,
        "quantity_sold": 3,
        "sales_starts_at": "2024-01-01T03:00:00Z",
        "sales_ends_at": "2024-01-01T03:00:00Z",
        "attributes": {},
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
        "event_id": "13e28612-f86c-5753-8964-2ed13f37a8b4",
        "id": "cfe667dc-16ef-5fb6-ad62-081427103900",
    },
    {
        "name": "ticket_types_name_4",
        "price_cents": 4,
        "quantity_total": 4,
        "quantity_sold": 4,
        "sales_starts_at": "2024-01-01T04:00:00Z",
        "sales_ends_at": "2024-01-01T04:00:00Z",
        "attributes": {},
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
        "event_id": "13e28612-f86c-5753-8964-2ed13f37a8b4",
        "id": "29f03bce-ffcc-57fc-bca0-cd5d6928f70f",
    },
    {
        "name": "ticket_types_name_5",
        "price_cents": 5,
        "quantity_total": 5,
        "quantity_sold": 5,
        "sales_starts_at": "2024-01-01T05:00:00Z",
        "sales_ends_at": "2024-01-01T05:00:00Z",
        "attributes": {},
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
        "event_id": "13e28612-f86c-5753-8964-2ed13f37a8b4",
        "id": "90d7da68-2ef2-5f04-9680-ff477876ba1c",
    },
]


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion from inline values to appropriate Python/DB values."""
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

    # Let the DB handle casting for GUID, dates, timestamptz, numerics, JSON, etc.
    return raw


def upgrade() -> None:
    """Seed fixed ticket_types rows inline.

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

    inserted = 0
    for raw_row in ROWS:
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

    log.info("Inserted %s rows into %s (inline seed)", inserted, TABLE_NAME)


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
