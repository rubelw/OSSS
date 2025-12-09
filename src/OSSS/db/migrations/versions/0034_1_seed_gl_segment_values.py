from __future__ import annotations

import logging
import csv
from pathlib import Path
import os
from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0034_1"
down_revision = "0034"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

SKIP_GL_SEGMENTS = os.getenv("SKIP_GL_SEGMENTS", "").lower() in ("1", "true", "yes", "on")

TABLE_NAME = "gl_segment_values"

# Path to CSV: ./raw_data/gl_segment_values.csv (relative to migrations root)
CSV_PATH = Path(__file__).resolve().parent.parent / "versions" / "raw_data" / "gl_segment_values.csv"


def _coerce_value(col: sa.Column, raw):
    """
    Best-effort coercion from Python/CSV value to appropriate DB-bound value.

    IMPORTANT: for string columns, keep empty strings as "" instead of converting
    them to NULL, so we don't violate NOT NULL constraints on name/code fields.
    """
    t = col.type

    # Handle None separately
    if raw is None:
        return None

    # Empty string handling depends on column type
    if raw == "":
        # For string-like columns, keep the empty string
        if isinstance(t, (sa.String, sa.Text)):
            return ""
        # For everything else, treat empty as NULL
        return None

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

    # Otherwise, pass raw through and let DB/SQLAlchemy cast
    return raw



def _load_seed_rows_from_csv() -> list[dict]:
    """Load seed rows for gl_segment_values from CSV file."""
    if not CSV_PATH.exists():
        log.warning("CSV file %s not found; skipping seed", CSV_PATH)
        return []

    rows: list[dict] = []
    with CSV_PATH.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Expecting at least: id, code, name, active, segment_id
            rows.append(row)

    if not rows:
        log.info("CSV %s is empty; no seed rows loaded", CSV_PATH)

    return rows


def upgrade() -> None:
    """Load seed data for gl_segment_values from CSV."""
    if SKIP_GL_SEGMENTS:
        log.warning("SKIP_GL_SEGMENTS flag is ON — skipping seeding for gl_segments")
        return

    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # Ensure target table exists
    if not inspector.has_table(TABLE_NAME):
        log.warning("Table %s does not exist; skipping seed", TABLE_NAME)
        return

    metadata = sa.MetaData()
    table = sa.Table(TABLE_NAME, metadata, autoload_with=bind)

    seed_rows = _load_seed_rows_from_csv()
    if not seed_rows:
        log.info("No seed rows defined for %s (CSV empty or missing)", TABLE_NAME)
        return

    inserted = 0
    for raw_row in seed_rows:
        values: dict = {}

        # Map & coerce by actual table columns
        for col in table.columns:
            if col.name not in raw_row:
                continue
            raw_val = raw_row[col.name]
            value = _coerce_value(col, raw_val)
            values[col.name] = value

        if not values:
            continue

        nested = bind.begin_nested()
        try:
            bind.execute(table.insert().values(**values))
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
        "Inserted %s rows into %s from %s",
        inserted,
        TABLE_NAME,
        CSV_PATH,
    )


def downgrade() -> None:
    """Best-effort removal of the seeded gl_segment_values rows based on CSV ids."""
    if SKIP_GL_SEGMENTS:
        log.warning("SKIP_GL_SEGMENTS flag is ON — skipping seeding for gl_segments")
        return

    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(TABLE_NAME):
        log.warning("Table %s does not exist; skipping delete", TABLE_NAME)
        return

    metadata = sa.MetaData()
    table = sa.Table(TABLE_NAME, metadata, autoload_with=bind)

    seed_rows = _load_seed_rows_from_csv()
    if not seed_rows:
        log.info("No seed rows loaded from CSV; nothing to delete for %s", TABLE_NAME)
        return

    ids = [row["id"] for row in seed_rows if "id" in row and row["id"]]
    if not ids:
        log.info("CSV had no ids; skipping delete for %s", TABLE_NAME)
        return

    bind.execute(table.delete().where(table.c.id.in_(ids)))
    log.info(
        "Deleted %s seeded rows from %s based on %s",
        len(ids),
        TABLE_NAME,
        CSV_PATH,
    )
