from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0005"
down_revision = "0004_rename_fields"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "organizations"

# Inline seed data
SEED_ROWS = [
    {
        "id": "c201e5e9-60c0-466f-8f63-aecbf868c420",
        "name": "Dallas Center-Grimes CSD",
        "short_name": "Dallas",
        "type": "district",
        "website": "https://org1.example.org",
        "phone": "515-555-5001",
    },
    {
        "id": "495c02aa-3e2e-4d4e-9623-7880d523bf71",
        "name": "Grimes Parks & Rec",
        "short_name": "Grimes",
        "type": "partner",
        "website": "https://org2.example.org",
        "phone": "515-555-5002",
    },
    {
        "id": "243e4944-068c-44f0-aa26-4ba25ff9339a",
        "name": "DCG Education Foundation",
        "short_name": "DCG",
        "type": "partner",
        "website": "https://org3.example.org",
        "phone": "515-555-5003",
    },
    {
        "id": "27ecfe2b-fe0d-4522-aa8a-ed65fd5f4419",
        "name": "Booster Club",
        "short_name": "Booster",
        "type": "partner",
        "website": "https://org4.example.org",
        "phone": "515-555-5004",
    },
    {
        "id": "a2e9b7f7-6fc8-48c4-950e-2300dc3f02fc",
        "name": "Local PTO Council",
        "short_name": "Local",
        "type": "partner",
        "website": "https://org5.example.org",
        "phone": "515-555-5005",
    },
]


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
    """Load seed data for organizations from inline SEED_ROWS.

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

        # Only include columns that exist on the table
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

    log.info("Inserted %s rows into %s from inline seed data", inserted, TABLE_NAME)


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
