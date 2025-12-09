from __future__ import annotations

import csv
import logging
from pathlib import Path
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

# Path to CSV: ./raw_data/gl_account_balances.csv (relative to migrations directory)
CSV_FILE = Path(__file__).resolve().parent.parent / "versions" / "raw_data" / "gl_account_balances.csv"


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion from CSV string to appropriate Python value."""
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
            log.warning("Invalid boolean for %s.%s: %r; using NULL", TABLE_NAME, col.name, raw)
            return None
        return bool(raw)

    # Numeric coercion (Decimal / NUMERIC)
    if isinstance(t, sa.Numeric):
        try:
            return raw if isinstance(raw, (int, float)) else float(raw)
        except Exception:
            log.warning("Invalid numeric for %s.%s: %r; using NULL", TABLE_NAME, col.name, raw)
            return None

    # JSON or dict: let SQLAlchemy parse string JSON automatically
    return raw


def upgrade() -> None:
    """Load seed data for gl_account_balances from CSV, with SAVEPOINT per row."""
    if SKIP_GL_SEGMENTS:
        log.warning("SKIP_GL_SEGMENTS flag is ON — skipping seeding for gl_segments")
        return

    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # Ensure table exists
    if not inspector.has_table(TABLE_NAME):
        log.warning("Table %s does not exist; skipping seed", TABLE_NAME)
        return

    # Ensure CSV exists
    if not CSV_FILE.exists():
        log.warning("CSV file not found for %s: %s; skipping", TABLE_NAME, CSV_FILE)
        return

    metadata = sa.MetaData()
    table = sa.Table(TABLE_NAME, metadata, autoload_with=bind)

    with CSV_FILE.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        log.info("CSV file for %s is empty: %s", TABLE_NAME, CSV_FILE)
        return

    inserted = 0

    for raw_row in rows:
        row = {}

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
                TABLE_NAME, exc, raw_row
            )

    log.info("Inserted %s rows into %s from %s", inserted, TABLE_NAME, CSV_FILE)


def downgrade() -> None:
    """
    No-op downgrade: consistent with other seed migrations.
    Seed data is left in place.
    """
    if SKIP_GL_SEGMENTS:
        log.warning("SKIP_GL_SEGMENTS flag is ON — skipping seeding for gl_segments")
        return

    pass
