from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "vendors"

SEED_ROWS = [
    {
        "id": "d7b782fe-058c-4344-b6db-15c5b7348607",
        "name": "ABC Janitorial",
        "category": "Facilities",
        "contact_name": "Contact 1",
        "phone": "515-555-8001",
        "email": "sales1@vendor-example.com",
    },
    {
        "id": "8f8c463b-197c-4412-9bc6-db7746bc2bb7",
        "name": "XYZ HVAC",
        "category": "Facilities",
        "contact_name": "Contact 2",
        "phone": "515-555-8002",
        "email": "sales2@vendor-example.com",
    },
    {
        "id": "5b77b96c-81a9-4579-b239-cb0c5164237f",
        "name": "Healthy Foods Co",
        "category": "Food",
        "contact_name": "Contact 3",
        "phone": "515-555-8003",
        "email": "sales3@vendor-example.com",
    },
    {
        "id": "7a490597-e033-4ff8-9cf5-2ca52767d0e9",
        "name": "Tech Solutions",
        "category": "Technology",
        "contact_name": "Contact 4",
        "phone": "515-555-8004",
        "email": "sales4@vendor-example.com",
    },
    {
        "id": "e6453423-425e-452c-9c2c-37c479b8216c",
        "name": "School Photography Inc",
        "category": "Services",
        "contact_name": "Contact 5",
        "phone": "515-555-8005",
        "email": "sales5@vendor-example.com",
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
    """Load seed data for vendors from inline SEED_ROWS.

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
        row = {}

        # Only include columns that actually exist on the table
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

    log.info(
        "Inserted %s rows into %s from inline seed data",
        inserted,
        TABLE_NAME,
    )


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
