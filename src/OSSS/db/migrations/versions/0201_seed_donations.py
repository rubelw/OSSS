from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0201"
down_revision = "0200"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "donations"

# Inline seed rows with realistic donation data
# Columns: donor_name, amount_cents, created_at, updated_at, school_id, campaign_id, id
SEED_ROWS = [
    {
        "donor_name": "Jordan Lee",
        "amount_cents": 2500,  # $25.00
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "campaign_id": "19624444-0ee7-5e2d-97a8-536a42e951b7",
        "id": "bf9fe137-f9de-5fda-aec4-904abc32f2e0",
    },
    {
        "donor_name": "Alex Martinez",
        "amount_cents": 5000,  # $50.00
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "campaign_id": "19624444-0ee7-5e2d-97a8-536a42e951b7",
        "id": "ab793044-489d-538f-9fba-5bbe486a1f0f",
    },
    {
        "donor_name": "Taylor Johnson",
        "amount_cents": 10000,  # $100.00
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "campaign_id": "19624444-0ee7-5e2d-97a8-536a42e951b7",
        "id": "398bc41c-fa71-51d8-ab5a-1cdc1eb4eba0",
    },
    {
        "donor_name": "Morgan Patel",
        "amount_cents": 15000,  # $150.00
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "campaign_id": "19624444-0ee7-5e2d-97a8-536a42e951b7",
        "id": "fbbb29a2-74f9-5f4e-92c9-a453ae968e23",
    },
    {
        "donor_name": "Riley Chen",
        "amount_cents": 25000,  # $250.00
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "campaign_id": "19624444-0ee7-5e2d-97a8-536a42e951b7",
        "id": "ddae1d62-7f5d-5b29-842b-ac39d7e2d2f1",
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

    # Otherwise, pass raw through and let DB cast (integers, timestamptz, UUID, etc.)
    return raw


def upgrade() -> None:
    """Load seed data for donations from inline SEED_ROWS.

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
