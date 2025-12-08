from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "education_associations"

SEED_ROWS = [
    {
        "id": "d611575d-a62c-41a1-a157-6434d34ffd8f",
        "name": "Iowa School Boards Association",
        "type": "professional",
        "state": "IA",
        "website": "https://example1.org",
    },
    {
        "id": "9e5c00fd-1a13-416d-b7ff-7c56181b140b",
        "name": "Midwest Superintendents Council",
        "type": "professional",
        "state": "IA",
        "website": "https://example2.org",
    },
    {
        "id": "0a820ac7-8550-4c18-a26a-8dcac9372e02",
        "name": "Regional Principals Network",
        "type": "professional",
        "state": "IA",
        "website": "https://example3.org",
    },
    {
        "id": "e815ea58-dc94-4438-931a-478714e65ba9",
        "name": "State Athletic Association",
        "type": "professional",
        "state": "IA",
        "website": "https://example4.org",
    },
    {
        "id": "210c95a2-0343-4732-afdf-b6857dc5fac4",
        "name": "Rural Schools Collaborative",
        "type": "professional",
        "state": "IA",
        "website": "https://example5.org",
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
    """Load seed data for education_associations from inline SEED_ROWS.

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
