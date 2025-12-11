from __future__ import annotations

import logging
import os

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0034_3"
down_revision = "0034_2"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

SKIP_GL_SEGMENTS = os.getenv("SKIP_GL_SEGMENTS", "").lower() in ("1", "true", "yes", "on")

TABLE_NAME = "gl_account_balances"

# Inline seed data for gl_account_balances
# Assumed columns:
#   id, account_id, fiscal_period_id,
#   beginning_balance, debits, credits, ending_balance, attributes
SEED_ROWS = [
    {
        "id": "3cd3eb91-ccf3-422d-b2a3-0fde282a934f",
        "account_id": "6a75aa46-a757-56fd-a8e3-53ada0559dad",
        "fiscal_period_id": "e03a4e59-941e-4c97-9d53-c4b72c77392e",
        "beginning_balance": "0.00",
        "debits": "100.00",
        "credits": "50.00",
        "ending_balance": "50.00",
        "attributes": {},  # JSONB
    },
    {
        "id": "0f306bbe-3fc7-4336-8c3c-84cf5488b5d0",
        "account_id": "b2b1b34f-2552-50d3-ad59-0db26521a897",
        "fiscal_period_id": "e03a4e59-941e-4c97-9d53-c4b72c77392e",
        "beginning_balance": "0.00",
        "debits": "100.00",
        "credits": "50.00",
        "ending_balance": "50.00",
        "attributes": {},  # JSONB
    },
]


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion from inline value to appropriate Python/DB value."""
    if raw is None or raw == "":
        return None

    t = col.type

    # Boolean coercion
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

    # Numeric coercion (Decimal / NUMERIC)
    if isinstance(t, sa.Numeric):
        try:
            return raw if isinstance(raw, (int, float)) else float(raw)
        except Exception:
            log.warning(
                "Invalid numeric for %s.%s: %r; using NULL",
                TABLE_NAME,
                col.name,
                raw,
            )
            return None

    # For JSON/JSONB, dicts, strings, etc., just pass through
    return raw


def upgrade() -> None:
    """Load seed data for gl_account_balances from inline SEED_ROWS."""
    if SKIP_GL_SEGMENTS:
        log.warning(
            "SKIP_GL_SEGMENTS flag is ON — skipping seeding for %s", TABLE_NAME
        )
        return

    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # Ensure table exists
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
        row: dict[str, object] = {}

        # Only use columns that exist on the SQL table
        for col in table.columns:
            if col.name not in raw_row:
                continue
            raw_val = raw_row[col.name]
            value = _coerce_value(col, raw_val)
            row[col.name] = value

        if not row:
            continue

        # Nested transaction → SAVEPOINT
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
    """
    No-op downgrade: consistent with other seed migrations.
    Seed data is left in place.
    """
    if SKIP_GL_SEGMENTS:
        log.warning(
            "SKIP_GL_SEGMENTS flag is ON — skipping downgrade operations for %s",
            TABLE_NAME,
        )
        return

    pass
