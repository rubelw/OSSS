from __future__ import annotations

import csv
import logging
import os

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0092"
down_revision = "0089"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "passes"
CSV_FILE = os.path.join(os.path.dirname(__file__), "csv", f"{TABLE_NAME}.csv")


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion from CSV string to appropriate Python value."""
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

    # Otherwise, pass raw through and let DB cast (Date, Integer, etc.)
    return raw


def upgrade() -> None:
    """Load seed data for {TABLE_NAME} from a CSV file.

    Each row is inserted inside an explicit nested transaction (SAVEPOINT)
    so a failing row won't abort the whole migration transaction.
    """
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(TABLE_NAME):
        log.warning("Table %s does not exist; skipping seed", TABLE_NAME)
        return

    if not os.path.exists(CSV_FILE):
        log.warning(
            "CSV file not found for %s: %s; skipping",
            TABLE_NAME,
            CSV_FILE,
        )
        return

    metadata = sa.MetaData()
    table = sa.Table(TABLE_NAME, metadata, autoload_with=bind)

    with open(CSV_FILE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        log.info("CSV file for %s is empty: %s", TABLE_NAME, CSV_FILE)
        return

    inserted = 0
    for raw_row in rows:
        row: dict[str, object] = {}

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

    log.info(
        "Inserted %s rows into %s from %s",
        inserted,
        TABLE_NAME,
        CSV_FILE,
    )


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
    # Seed data used for this migration (for reference):
    #
    # school_id,name,description,price_cents,valid_from,valid_to,max_uses,id,created_at,updated_at
    # af33eba3-d881-554e-9b43-2a7ea376e1f0,High School All-Sport Student Pass,"Admits one high school student to all regular-season home athletic events for the 2024–2025 school year.",7500,2024-08-15,2025-05-31,999,990db334-3684-5ecb-86fa-2a5a5c046e17,2024-01-01T01:00:00Z,2024-01-01T01:00:00Z
    # 119caaef-ef97-5364-b179-388e108bd40d,Middle School Activity Pass,"Admits one middle school student to all regular-season home games, concerts, and performances.",4000,2024-08-20,2025-05-31,999,9365d115-1f2c-5c21-a78f-86683c17a03f,2024-01-01T02:00:00Z,2024-01-01T02:00:00Z
    # b122fcb4-2864-593c-9b05-2188ef296db4,South Prairie Family Event Pass,"Family pass for up to four household members to attend South Prairie evening events (music programs, STEM nights, and family celebrations).",2500,2024-09-01,2025-05-31,30,f39841c0-c085-56ca-8faf-c67fa1806e53,2024-01-01T03:00:00Z,2024-01-01T03:00:00Z
    # df4b1423-d755-5c7f-a0ba-6908de77f61b,Heritage Elementary Performance Pass,"Admits one adult and one student to all Heritage Elementary music programs and fine arts performances.",2000,2024-09-01,2025-05-31,20,5e1a2113-f8bf-5f93-993b-aae48e68a4af,2024-01-01T04:00:00Z,2024-01-01T04:00:00Z
    # 634b8058-d620-5a5c-86b5-c0794d3a3b73,North Ridge Family Athletics Pass,"Family pass for entry to North Ridge home athletic events (basketball, volleyball, and track) for the 2024–2025 school year.",3000,2024-08-25,2025-05-31,40,0a30c610-413e-5d76-a930-af3b67258651,2024-01-01T05:00:00Z,2024-01-01T05:00:00Z
