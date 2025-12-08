from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "roles"

SEED_ROWS = [
    {
        "id": "f544f901-921e-471f-a62a-06bb6616a80b",
        "name": "Teacher",
        "description": "Teacher role in district system.",
        "is_system_role": False,
    },
    {
        "id": "0dd7067c-139a-463c-b12b-377dfabb1fed",
        "name": "Principal",
        "description": "Principal role in district system.",
        "is_system_role": False,
    },
    {
        "id": "b213323b-7e44-465c-bf7e-302713c9f26d",
        "name": "Superintendent",
        "description": "Superintendent role in district system.",
        "is_system_role": True,
    },
    {
        "id": "bc6112e7-6337-4942-b495-368ea212efa9",
        "name": "Board Member",
        "description": "Board Member role in district system.",
        "is_system_role": False,
    },
    {
        "id": "780a50b2-633c-4e5e-b35c-00b248c6a61e",
        "name": "System Admin",
        "description": "System Admin role in district system.",
        "is_system_role": True,
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
    """Load seed data for roles from inline SEED_ROWS.

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
