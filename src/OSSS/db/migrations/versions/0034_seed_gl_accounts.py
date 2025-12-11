from __future__ import annotations

import logging
import os

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0034"
down_revision = "0033"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

SKIP_GL_SEGMENTS = os.getenv("SKIP_GL_SEGMENTS", "").lower() in ("1", "true", "yes", "on")

TABLE_NAME = "gl_accounts"

# Inline seed data for gl_accounts
# Columns: id, code, name, acct_type, active, attributes
SEED_ROWS = [
    {
        "id": "6a75aa46-a757-56fd-a8e3-53ada0559dad",
        "code": "10-1000-000-100-0000-000",
        "name": "General Fund / Instruction / Regular Education / Salaries / No Project / General",
        "acct_type": "expense",
        "active": True,
        "attributes": None,
    },
    {
        "id": "b2b1b34f-2552-50d3-ad59-0db26521a897",
        "code": "10-1000-000-100-0000-810",
        "name": "General Fund / Instruction / Regular Education / Salaries / Instructional Support Levy (ISL)",
        "acct_type": "expense",
        "active": True,
        "attributes": None,
    },

]


def _coerce_value(col: sa.Column, raw):
    """
    Best-effort coercion from inline value to the DB type.

    This is mostly relevant for booleans, but will happily pass
    through strings, dict-like JSON, etc. for the DB to handle.
    """
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

    # Let DB/SQLAlchemy handle other types (String, JSONB, etc.)
    return raw


def upgrade() -> None:
    """Load seed data for gl_accounts from inline SEED_ROWS."""
    if SKIP_GL_SEGMENTS:
        log.warning("SKIP_GL_SEGMENTS flag is ON — skipping seeding for gl_accounts")
        return

    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(TABLE_NAME):
        log.warning("Table %s does not exist; skipping seed", TABLE_NAME)
        return

    if not SEED_ROWS:
        log.info("No inline seed rows defined for %s; nothing to insert", TABLE_NAME)
        return

    metadata = sa.MetaData()
    table = sa.Table(TABLE_NAME, metadata, autoload_with=bind)

    inserted = 0
    for raw_row in SEED_ROWS:
        row: dict = {}

        # Only pass columns that actually exist on gl_accounts
        for col in table.columns:
            if col.name not in raw_row:
                continue
            raw_val = raw_row[col.name]
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

    log.info("Inserted %s inline seed rows into %s", inserted, TABLE_NAME)


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    if SKIP_GL_SEGMENTS:
        log.warning("SKIP_GL_SEGMENTS flag is ON — skipping delete for gl_accounts")
        return

    # If you later want to delete these rows explicitly, you could
    # add a delete by id here. For now, we leave the seed data in place.
    pass
