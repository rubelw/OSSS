from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "addresses"

SEED_ROWS = [
    {
        "id": "040fe6e6-291a-48ea-b609-42435a3e850e",
        "line1": "101 Main St",
        "line2": "",
        "city": "Dallas Center",
        "state": "IA",
        "postal_code": "50101",
        "country": "US",
    },
    {
        "id": "16beb5bf-6db4-4335-aa19-3223e3f65c2f",
        "line1": "102 Main St",
        "line2": "Apt 2B",
        "city": "Dallas Center",
        "state": "IA",
        "postal_code": "50102",
        "country": "US",
    },
    {
        "id": "8d6e5552-5b71-4627-8542-8f99ed03b091",
        "line1": "103 Main St",
        "line2": "",
        "city": "Dallas Center",
        "state": "IA",
        "postal_code": "50103",
        "country": "US",
    },
    {
        "id": "b8ac9d0b-f00b-4e24-ae86-2e2342df175c",
        "line1": "104 Main St",
        "line2": "Apt 4B",
        "city": "Dallas Center",
        "state": "IA",
        "postal_code": "50104",
        "country": "US",
    },
    {
        "id": "b3a21988-dffd-4ea8-9e93-79be93586e0d",
        "line1": "105 Main St",
        "line2": "",
        "city": "Dallas Center",
        "state": "IA",
        "postal_code": "50105",
        "country": "US",
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
    """Load seed data for addresses from inline SEED_ROWS.

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
