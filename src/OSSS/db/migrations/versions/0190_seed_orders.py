from __future__ import annotations

import csv  # kept for consistency with other migrations
import logging
import os

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0190"
down_revision = "0189"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "orders"
CSV_FILE = os.path.join(os.path.dirname(__file__), "csv", f"{TABLE_NAME}.csv")

# Inline, realistic seed data for orders
SEED_ROWS = [
    {
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "event_id": "13e28612-f86c-5753-8964-2ed13f37a8b4",
        "purchaser_user_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "buyer_name": "Jordan Smith",
        "buyer_email": "jordan.smith@example.edu",
        "total_cents": 4000,  # $40.00
        "currency": "USD",
        "status": "paid",
        "external_ref": "ORD-2024-0001",
        "attributes": {
            "source": "online_portal",
            "payment_method": "credit_card",
        },
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
        "id": "c4f8bc7f-a2ef-5587-b637-901a3096acec",
    },
    {
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "event_id": "13e28612-f86c-5753-8964-2ed13f37a8b4",
        "purchaser_user_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "buyer_name": "Alex Rivera",
        "buyer_email": "alex.rivera@example.edu",
        "total_cents": 2000,  # $20.00
        "currency": "USD",
        "status": "paid",
        "external_ref": "ORD-2024-0002",
        "attributes": {
            "source": "box_office",
            "payment_method": "cash",
        },
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
        "id": "b99d68b1-deae-5a15-9021-9ed98db58af9",
    },
    {
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "event_id": "13e28612-f86c-5753-8964-2ed13f37a8b4",
        "purchaser_user_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "buyer_name": "Taylor Lee",
        "buyer_email": "taylor.lee@example.edu",
        "total_cents": 3000,  # $30.00
        "currency": "USD",
        "status": "pending",
        "external_ref": "ORD-2024-0003",
        "attributes": {
            "source": "online_portal",
            "payment_method": "credit_card",
        },
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
        "id": "0f9dc12d-8b51-5657-be81-ac9b9c2d0e6a",
    },
    {
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "event_id": "13e28612-f86c-5753-8964-2ed13f37a8b4",
        "purchaser_user_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "buyer_name": "Morgan Patel",
        "buyer_email": "morgan.patel@example.edu",
        "total_cents": 5000,  # $50.00
        "currency": "USD",
        "status": "refunded",  # <= 8 chars
        "external_ref": "ORD-2024-0004",
        "attributes": {
            "source": "online_portal",
            "refund_reason": "weather_cancellation",
        },
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
        "id": "9ac060ad-a9b8-5978-b7a9-19000b86a93f",
    },
    {
        # previously status="cancelled" (9 chars) -> VARCHAR(8) overflow
        # use "refunded" (8 chars) instead, consistent with a cancelled/returned order
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "event_id": "13e28612-f86c-5753-8964-2ed13f37a8b4",
        "purchaser_user_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "buyer_name": "Casey Nguyen",
        "buyer_email": "casey.nguyen@example.edu",
        "total_cents": 6000,  # $60.00
        "currency": "USD",
        "status": "refunded",  # ✅ fits VARCHAR(8)
        "external_ref": "ORD-2024-0005",
        "attributes": {
            "source": "online_portal",
            "refund_reason": "buyer_requested",
        },
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
        "id": "acf91972-4bde-5069-bbad-f981491a1f00",
    },
]


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion from CSV string to appropriate Python value.

    Kept for consistency with other migrations, though not used with inline data.
    """
    if raw == "" or raw is None:
        return None

    t = col.type

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

    return raw


def upgrade() -> None:
    """Load seed data for orders from inline SEED_ROWS."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(TABLE_NAME):
        log.warning("Table %s does not exist; skipping seed", TABLE_NAME)
        return

    metadata = sa.MetaData()
    table = sa.Table(TABLE_NAME, metadata, autoload_with=bind)

    inserted = 0
    for raw_row in SEED_ROWS:
        row = {col.name: raw_row[col.name] for col in table.columns if col.name in raw_row}

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

    log.info(
        "Inserted %s rows into %s from inline SEED_ROWS",
        inserted,
        TABLE_NAME,
    )


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
