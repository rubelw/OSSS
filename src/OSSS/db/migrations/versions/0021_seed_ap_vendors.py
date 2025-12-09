from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "ap_vendors"

SEED_ROWS = [
    {
        "id": "7b6b1bfc-7a46-4b9b-9cc9-ad125b88f317",
        "vendor_name": "School Specialty",
        "account_number": "ACCT-1001",
        "phone": "515-555-1001",
        "email": "billing1@example-vendor.com",
        "address_line1": "201 Supply Ave",
        "city": "Grimes",
        "state": "IA",
        "postal_code": "50201",
    },
    {
        "id": "bcab4ec5-d430-43bf-9906-6726f509130a",
        "vendor_name": "Edutech Supplies",
        "account_number": "ACCT-1002",
        "phone": "515-555-1002",
        "email": "billing2@example-vendor.com",
        "address_line1": "202 Supply Ave",
        "city": "Grimes",
        "state": "IA",
        "postal_code": "50202",
    },
    {
        "id": "3900131a-f01f-4772-9519-9cd8bbb9f701",
        "vendor_name": "Midwest Classroom Co",
        "account_number": "ACCT-1003",
        "phone": "515-555-1003",
        "email": "billing3@example-vendor.com",
        "address_line1": "203 Supply Ave",
        "city": "Grimes",
        "state": "IA",
        "postal_code": "50203",
    },
    {
        "id": "8ccce12d-7bd4-40fe-a32f-4718a2813c9f",
        "vendor_name": "Campus Office Depot",
        "account_number": "ACCT-1004",
        "phone": "515-555-1004",
        "email": "billing4@example-vendor.com",
        "address_line1": "204 Supply Ave",
        "city": "Grimes",
        "state": "IA",
        "postal_code": "50204",
    },
    {
        "id": "59f6c79b-be0d-4bdc-accd-3b8991a1c382",
        "vendor_name": "Learning Lab Inc",
        "account_number": "ACCT-1005",
        "phone": "515-555-1005",
        "email": "billing5@example-vendor.com",
        "address_line1": "205 Supply Ave",
        "city": "Grimes",
        "state": "IA",
        "postal_code": "50205",
    },
]


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion from inline value to appropriate DB value."""
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

    # Otherwise, pass raw through and let DB cast
    return raw


def upgrade() -> None:
    """Load seed data for ap_vendors from inline SEED_ROWS.

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

        # Only include columns that actually exist on the table
        for col in table.columns:
            raw_val = None

            # 1) Direct match from SEED_ROWS, if present
            if col.name in raw_row:
                raw_val = raw_row[col.name]

            # 2) Special mappings to your actual schema
            elif col.name == "vendor_no":
                # derive vendor_no from account_number or vendor_no, or fallback
                raw_val = (
                    raw_row.get("account_number")
                    or raw_row.get("vendor_no")
                    or f"V-{raw_row['id'][:8]}"
                )
            elif col.name == "name" and "vendor_name" in raw_row:
                raw_val = raw_row["vendor_name"]
            elif col.name == "address1" and "address_line1" in raw_row:
                raw_val = raw_row["address_line1"]
            elif col.name == "active":
                # ensure NOT NULL; default to True if not explicitly provided
                raw_val = raw_row.get("active", True)

            # 3) Let created_at, updated_at, JSON fields, etc. use defaults
            else:
                continue

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

    log.info(
        "Inserted %s rows into %s from inline seed data",
        inserted,
        TABLE_NAME,
    )


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
