from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "attendance_codes"

SEED_ROWS = [
    {
        "id": "b67410c9-0006-441a-a165-f65ea1d10f44",
        "code": "P",
        "description": "Present",
        "is_present": True,
        "is_excused": False,
    },
    {
        "id": "30f7945f-59da-4212-bf01-22995cf9e5b2",
        "code": "A",
        "description": "Unexcused absence",
        "is_present": False,
        "is_excused": False,
    },
    {
        "id": "9fc369ea-5911-43c7-b604-29e339aa3424",
        "code": "E",
        "description": "Excused absence",
        "is_present": False,
        "is_excused": True,
    },
    {
        "id": "fb75d0f5-8b4a-4148-b687-5c4a7630b0cc",
        "code": "T",
        "description": "Tardy",
        "is_present": True,
        "is_excused": False,
    },
    {
        "id": "2fdf252f-f8a4-454a-8019-aa0fc992cb76",
        "code": "S",
        "description": "School activity",
        "is_present": True,
        "is_excused": True,
    },
]


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion from CSV-style value to appropriate Python value."""
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
    """Load seed data for attendance_codes from inline SEED_ROWS.

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
