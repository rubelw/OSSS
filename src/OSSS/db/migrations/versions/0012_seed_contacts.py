from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "contacts"

SEED_ROWS = [
    {
        "id": "334d4a32-2324-4ebe-80e4-1f4166d9806d",
        "first_name": "Contact1",
        "last_name": "Parent",
        "email": "parent1@familymail.com",
        "phone": "515-555-3001",
        "type": "guardian",
    },
    {
        "id": "54c8dfad-88b6-46b7-aebf-77cea3c3c3be",
        "first_name": "Contact2",
        "last_name": "Parent",
        "email": "parent2@familymail.com",
        "phone": "515-555-3002",
        "type": "guardian",
    },
    {
        "id": "3e2cc481-02dc-46fe-9103-3eff18ce0cfa",
        "first_name": "Contact3",
        "last_name": "Parent",
        "email": "parent3@familymail.com",
        "phone": "515-555-3003",
        "type": "guardian",
    },
    {
        "id": "3c1fc329-93c8-41fb-bbcf-8759cfd85168",
        "first_name": "Contact4",
        "last_name": "Parent",
        "email": "parent4@familymail.com",
        "phone": "515-555-3004",
        "type": "guardian",
    },
    {
        "id": "53dd19d3-6604-4c52-b8f6-2ad28cb3f3b4",
        "first_name": "Contact5",
        "last_name": "Parent",
        "email": "parent5@familymail.com",
        "phone": "515-555-3005",
        "type": "guardian",
    },
]


def _derive_value(raw_row: dict) -> str:
    """
    Derive the NOT NULL `value` column for contacts.

    Prefer email, then phone, then 'First Last', then a simple fallback.
    """
    email = raw_row.get("email")
    phone = raw_row.get("phone")
    first = (raw_row.get("first_name") or "").strip()
    last = (raw_row.get("last_name") or "").strip()

    if email:
        return email
    if phone:
        return phone

    name = " ".join(p for p in (first, last) if p)
    if name:
        return name

    # Final fallback – should rarely be used
    return f"contact-{raw_row.get('id', 'unknown')}"


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion from CSV-style string to appropriate Python value."""
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
    """Load seed data for contacts from inline SEED_ROWS.

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

        for col in table.columns:
            # Always populate NOT NULL `value` even though it's not in SEED_ROWS
            if col.name == "value":
                raw_val = _derive_value(raw_row)
                value = _coerce_value(col, raw_val)
                row[col.name] = value
                continue

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
