from __future__ import annotations

import logging
from datetime import datetime

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0030"
down_revision = "0029"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "users"

SEED_ROWS = [
    {
        "id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "username": "michaelsmith",
        "email": "michaelsmith@dcgschools.org",
        "role_name": "Teacher",
        "is_active": "true",
    },
    {
        "id": "861af025-3009-4c30-8455-644ae633c497",
        "username": "sarahjohnson",
        "email": "sarahjohnson@dcgschools.org",
        "role_name": "Principal",
        "is_active": "true",
    },
    {
        "id": "e2d66cd0-b0c1-4f8d-b1a7-faef4804f7d9",
        "username": "jameswilliams",
        "email": "jameswilliams@dcgschools.org",
        "role_name": "Superintendent",
        "is_active": "true",
    },
    {
        "id": "22838cc6-88af-472f-9723-2ef1b2804d6e",
        "username": "emilybrown",
        "email": "emilybrown@dcgschools.org",
        "role_name": "Board Member",
        "is_active": "true",
    },
    {
        "id": "ca72277c-0b76-4560-b6aa-3eb616efe63e",
        "username": "davidjones",
        "email": "davidjones@dcgschools.org",
        "role_name": "System Admin",
        "is_active": "true",
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
    """Load seed data for users from inline SEED_ROWS.

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
        # single timestamp for both created_at and updated_at
        now = datetime.utcnow()
        row: dict[str, object] = {}

        for col in table.columns:
            raw_val = None

            # direct match
            if col.name in raw_row:
                raw_val = raw_row[col.name]

            # fill timestamp columns explicitly if present
            elif col.name in ("created_at", "updated_at"):
                raw_val = now

            else:
                # let DB defaults handle anything else
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

    log.info("Inserted %s rows into %s from inline seed data", inserted, TABLE_NAME)


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
