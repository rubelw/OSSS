from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "seasons"

SEED_ROWS = [
    {
        "id": "c39ad8bc-6fea-4025-9a5f-d1887a04fe6c",
        "name": "Fall",
        "school_year": "2024-2025",
        "start_date": "2024-08-31",
        "end_date": "2024-10-30",
    },
    {
        "id": "4f06cf11-c86d-4ba5-9fd1-b04e2474ded7",
        "name": "Winter",
        "school_year": "2024-2025",
        "start_date": "2024-09-30",
        "end_date": "2024-11-29",
    },
    {
        "id": "cc1999cc-7e3e-48de-8d4e-eba85196f3e0",
        "name": "Spring",
        "school_year": "2024-2025",
        "start_date": "2024-10-30",
        "end_date": "2024-12-29",
    },
    {
        "id": "0928bc8b-81b1-43fc-a529-38545ee46cdd",
        "name": "Summer",
        "school_year": "2024-2025",
        "start_date": "2024-11-29",
        "end_date": "2025-01-28",
    },
    {
        "id": "f463345f-0988-4dfb-b92f-233b3dc79805",
        "name": "Year-Round",
        "school_year": "2024-2025",
        "start_date": "2024-12-29",
        "end_date": "2025-02-27",
    },
]


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion from CSV-style string / Python value to appropriate DB value."""
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

    # Otherwise, pass raw through and let DB cast (e.g. dates, ints, enums)
    return raw


def _derive_year(raw_row: dict) -> int | None:
    """
    Derive an integer 'year' from either school_year ('2024-2025') or start_date ('2024-08-31').
    """
    school_year = raw_row.get("school_year")
    if school_year:
        try:
            # e.g. "2024-2025" -> 2024
            return int(str(school_year).split("-")[0])
        except (ValueError, TypeError):
            pass

    start_date = raw_row.get("start_date")
    if start_date:
        try:
            # e.g. "2024-08-31" -> 2024
            return int(str(start_date).split("-")[0])
        except (ValueError, TypeError):
            pass

    return None


def upgrade() -> None:
    """Load seed data for seasons from inline SEED_ROWS.

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
            # Special handling for the NOT NULL 'year' column
            if col.name == "year":
                year_val = _derive_year(raw_row)
                if year_val is None:
                    log.warning(
                        "Could not derive 'year' for seasons row %s; skipping row.",
                        raw_row,
                    )
                    row = {}  # force skip
                    break
                raw_val = year_val
            elif col.name in raw_row:
                raw_val = raw_row[col.name]
            else:
                # Let created_at/updated_at use server defaults; skip any
                # extra columns not present in the seed dict.
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
