from __future__ import annotations

import csv
import logging
import os
from pathlib import Path

from datetime import datetime  # still fine to keep, even if unused

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0032"
down_revision = "0030"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "fiscal_years"
CSV_FILE = Path(__file__).resolve().parent.parent / "versions" / "raw_data" / "fiscal_years.csv"


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion from CSV/inline value to appropriate DB value."""
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

    # Otherwise, pass raw through and let DB cast (dates, enums, etc.)
    return raw


def _compute_year(raw_row: dict) -> int | None:
    """
    Derive the integer fiscal year.

    Default: take it from the start_date year (e.g. 2023-07-01 -> 2023).
    If you prefer the ending year instead, switch to end_date.

    Fallback: try name like "2023-2024".
    """
    start = raw_row.get("start_date")
    if isinstance(start, str) and len(start) >= 4:
        try:
            return int(start[:4])
        except ValueError:
            pass

    # Fallback: try name like "2023-2024"
    name = raw_row.get("name")
    if isinstance(name, str) and len(name) >= 4:
        try:
            return int(name[:4])
        except ValueError:
            pass

    return None


def _compute_is_closed(raw_row: dict) -> bool:
    """
    Map from is_current -> is_closed.

    If is_current is truthy, then not closed.
    Everything else => closed.
    """
    raw = raw_row.get("is_current")
    if isinstance(raw, str):
        v = raw.strip().lower()
        is_current = v in ("true", "t", "1", "yes", "y")
    else:
        is_current = bool(raw)

    return not is_current


def upgrade() -> None:
    """Load seed data for fiscal_years from ./raw_data/fiscal_years.csv.

    Each row is inserted inside an explicit nested transaction (SAVEPOINT)
    so a failing row won't abort the whole migration transaction.
    """
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(TABLE_NAME):
        log.warning("Table %s does not exist; skipping seed", TABLE_NAME)
        return

    if not os.path.exists(CSV_FILE):
        log.warning("CSV file not found for %s: %s; skipping", TABLE_NAME, CSV_FILE)
        return

    with open(CSV_FILE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        log.info("CSV file for %s is empty: %s; skipping", TABLE_NAME, CSV_FILE)
        return

    metadata = sa.MetaData()
    table = sa.Table(TABLE_NAME, metadata, autoload_with=bind)

    inserted = 0
    for raw_row in rows:
        row: dict[str, object] = {}

        for col in table.columns:
            raw_val = None

            # 1) Direct match if present (e.g., id, name, start_date, end_date, is_closed, year)
            if col.name in raw_row and raw_row[col.name] != "":
                raw_val = raw_row[col.name]

            # 2) Special mappings for this schema
            elif col.name == "year":
                raw_val = _compute_year(raw_row)

            elif col.name == "is_closed":
                # Prefer explicit is_closed if present in CSV
                if "is_closed" in raw_row and raw_row["is_closed"] != "":
                    raw_val = raw_row["is_closed"]
                else:
                    raw_val = _compute_is_closed(raw_row)

            # Let created_at/updated_at use server defaults from TimestampMixin
            else:
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

    log.info(
        "Inserted %s rows into %s from CSV file %s",
        inserted,
        TABLE_NAME,
        CSV_FILE,
    )


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
