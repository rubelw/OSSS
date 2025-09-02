# src/OSSS/db/migrations/versions/0092_populate_att_evts.py
from __future__ import annotations

import csv
import logging
import os
import random
import uuid
from datetime import date, timedelta, datetime, timezone
from typing import List, Dict, Tuple

from alembic import op
import sqlalchemy as sa

# ---- Alembic identifiers ----
revision = "0094_seed_calendars"
down_revision = "0093_seed_behavior_int"  # update if needed
branch_labels = None
depends_on = None

# ---- Logging ---------------------------------------------------------------
log = logging.getLogger("alembic.runtime.migration")


# ---- Config / knobs ----
CSV_FILENAME = "calendars.csv"
# If you want to cap how many rows get created; by default we do at least 1 per school.
DEFAULT_ROW_COUNT = int(os.getenv("CALENDAR_ROWS", "0"))  # 0 = no cap
SEED = os.getenv("CALENDAR_SEED")  # e.g., "42" for reproducible names

# ---- Helpers ---------------------------------------------------------------

def _csv_path() -> str:
    """Write/read the CSV in the same folder as this migration file."""
    return os.path.join(os.path.dirname(__file__), CSV_FILENAME)

def _fetch_all_scalar(conn, sql: str) -> List[str]:
    return [r[0] for r in conn.execute(sa.text(sql)).fetchall()]

def _fetch_school_ids(conn) -> List[str]:
    schools = _fetch_all_scalar(conn, "SELECT id FROM schools")
    if not schools:
        raise RuntimeError("No schools found; cannot populate calendars.")
    log.info("[populate_calendars] Found %d schools.", len(schools))
    return schools

def _generate_rows(school_ids: List[str], max_rows: int | None) -> List[Dict[str, object]]:
    """
    Create at least one calendar per school; optionally add more up to max_rows (if provided).
    """
    if SEED is not None:
        try:
            random.seed(int(SEED))
        except ValueError:
            random.seed(SEED)

    now = datetime.now(timezone.utc)
    this_year = date.today().year
    next_year = this_year + 1

    base_names = [
        f"{this_year}-{next_year} Academic Calendar",
        f"{this_year}-{next_year} School Events",
        f"{this_year}-{next_year} Holiday Calendar",
    ]

    rows: List[Dict[str, object]] = []

    # 1) Guarantee at least 1 per school
    for sid in school_ids:
        name = random.choice(base_names)
        rows.append(
            {
                "id": str(uuid.uuid4()),
                "school_id": sid,
                "name": name,
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
            }
        )

    # 2) If a cap is set and we can add more rows, sprinkle extras
    if max_rows and max_rows > len(rows):
        extras_needed = max_rows - len(rows)
        variants = [
            f"{this_year}-{next_year} Athletics Calendar",
            f"{this_year}-{next_year} Testing Calendar",
            f"{this_year}-{next_year} PD / In-Service Days",
            f"{this_year}-{next_year} Activities & Clubs",
        ]
        for _ in range(extras_needed):
            sid = random.choice(school_ids)
            name = random.choice(base_names + variants)
            rows.append(
                {
                    "id": str(uuid.uuid4()),
                    "school_id": sid,
                    "name": name,
                    "created_at": now.isoformat(),
                    "updated_at": now.isoformat(),
                }
            )

    log.info(
        "[populate_calendars] Generated %d calendar rows (schools=%d, cap=%s).",
        len(rows), len(school_ids), max_rows if max_rows else "none",
    )
    return rows

def _write_csv(csv_path: str, rows: List[Dict[str, object]]) -> None:
    fieldnames = ["id", "school_id", "name", "created_at", "updated_at"]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    log.info("[populate_calendars] Wrote CSV: %s (%d rows).", csv_path, len(rows))

def _read_csv(csv_path: str) -> List[Dict[str, object]]:
    with open(csv_path, "r", newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        data = list(r)
    log.info("[populate_calendars] Read CSV: %s (%d rows).", csv_path, len(data))
    return data

# ---- Migration ops ---------------------------------------------------------

def upgrade():
    conn = op.get_bind()

    # 1) Gather reference data
    school_ids = _fetch_school_ids(conn)

    # 2) Generate rows & write CSV (always rewrite so it’s deterministic per-run with SEED)
    max_rows = DEFAULT_ROW_COUNT if DEFAULT_ROW_COUNT > 0 else None
    rows = _generate_rows(school_ids, max_rows)
    csv_path = _csv_path()
    _write_csv(csv_path, rows)

    # 3) Clear table to be idempotent
    log.info("[populate_calendars] Clearing calendars table (DELETE).")
    conn.execute(sa.text("DELETE FROM calendars"))

    # 4) Read CSV and bulk insert
    data = _read_csv(csv_path)

    calendars_tbl = sa.table(
        "calendars",
        sa.column("id", sa.String),
        sa.column("school_id", sa.String),
        sa.column("name", sa.Text),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )

    to_insert = []
    for r in data:
        to_insert.append(
            {
                "id": r["id"],
                "school_id": r["school_id"],
                "name": r["name"],
                "created_at": datetime.fromisoformat(r["created_at"]),
                "updated_at": datetime.fromisoformat(r["updated_at"]),
            }
        )

    CHUNK = 1000
    for i in range(0, len(to_insert), CHUNK):
        op.bulk_insert(calendars_tbl, to_insert[i : i + CHUNK])
        log.info("[populate_calendars] Inserted rows %d..%d", i + 1, min(i + CHUNK, len(to_insert)))

    log.info("[populate_calendars] Done. Inserted %d calendars.", len(to_insert))

def downgrade():
    conn = op.get_bind()
    log.info("[populate_calendars] Downgrade: clearing calendars table.")
    conn.execute(sa.text("DELETE FROM calendars"))