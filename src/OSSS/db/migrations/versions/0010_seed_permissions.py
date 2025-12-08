from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "permissions"

SEED_ROWS = [
    {
        "id": "693b9196-db9c-4c2d-bf3c-6345c3ec00de",
        "code": "VIEW_STUDENTS",
        "description": "View Students",
        "default_for_role": "Teacher",
    },
    {
        "id": "c8fe61da-0ca0-43e8-bcdc-e25a33f0a0d2",
        "code": "EDIT_STUDENTS",
        "description": "Edit Students",
        "default_for_role": "Admin",
    },
    {
        "id": "88203b7d-40c7-439f-bafd-69e332416ebe",
        "code": "VIEW_FINANCE",
        "description": "View Finance",
        "default_for_role": "Teacher",
    },
    {
        "id": "3ee449de-d487-40f2-9710-0c0dd1700c6e",
        "code": "EDIT_FINANCE",
        "description": "Edit Finance",
        "default_for_role": "Admin",
    },
    {
        "id": "2c273d41-756c-4b99-9a41-2eca00118108",
        "code": "MANAGE_USERS",
        "description": "Manage Users",
        "default_for_role": "Admin",
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
    """Load seed data for permissions from inline SEED_ROWS.

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
