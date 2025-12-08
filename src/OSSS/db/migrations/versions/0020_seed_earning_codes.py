from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "earning_codes"

SEED_ROWS = [
    {
        "id": "03e943d9-b3a2-471b-80d7-612f7434dc8b",
        "code": "REG",
        "description": "Regular hourly pay",
        "is_overtime": "false",
    },
    {
        "id": "5721250e-901b-49ba-ac78-df79fa4e5e87",
        "code": "OT",
        "description": "Overtime pay",
        "is_overtime": "true",
    },
    {
        "id": "4928d8e7-b200-4acb-9150-4a269d6f4262",
        "code": "STIP",
        "description": "Stipend",
        "is_overtime": "false",
    },
    {
        "id": "acfcddbd-ca6f-46bd-a103-2d465ee73a26",
        "code": "SUB",
        "description": "Substitute teacher pay",
        "is_overtime": "false",
    },
    {
        "id": "25206f5e-ca08-4764-ba9a-e1dda6ba9a00",
        "code": "COACH",
        "description": "Coaching supplement",
        "is_overtime": "false",
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

    # Otherwise, pass raw through and let DB cast (e.g. enums, ints, dates)
    return raw


def upgrade() -> None:
    """Load seed data for earning_codes from inline SEED_ROWS.

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
            # Special handling for NOT NULL 'name' column which isn't in SEED_ROWS
            if col.name == "name":
                # Prefer explicit name if present; otherwise derive from description or code
                raw_val = (
                    raw_row.get("name")
                    or raw_row.get("description")
                    or raw_row.get("code")
                )
                if raw_val is None:
                    log.warning(
                        "Could not derive 'name' for earning_codes row %s; skipping row.",
                        raw_row,
                    )
                    row = {}  # force skip
                    break
            elif col.name in raw_row:
                raw_val = raw_row[col.name]
            else:
                # Let created_at / updated_at / other columns use defaults if they exist
                continue

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
