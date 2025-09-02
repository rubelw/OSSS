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
revision = "0095_seed_calendar_dy"
down_revision = "0094_seed_calendars"  # update if needed
branch_labels = None
depends_on = None

# ---- Logging ---------------------------------------------------------------
log = logging.getLogger("alembic.runtime.migration")


# --- Config / knobs ---
CSV_FILENAME = "calendar_days.csv"

# Total rows target (upper bound). We’ll also cap by (#calendars * #days_in_range).
DEFAULT_ROW_COUNT = int(os.getenv("CALDAY_ROWS", "4000"))

# RNG seed for reproducibility (unset for true randomness)
SEED = os.getenv("CALDAY_SEED")  # e.g. "42"

# Sample over the last ~9 months by default
END_DATE = date.today()
START_DATE = END_DATE - timedelta(days=int(os.getenv("CALDAY_SPAN_DAYS", "270")))

# Distribution of day types (only used for Mon–Fri; weekends are auto-labeled)
DAY_TYPES = [
    ("instructional", 0.80),
    ("holiday",       0.05),
    ("inservice",     0.05),
    ("break",         0.07),
    ("other",         0.03),
]

# --- Helpers -------------------------------------------------------------------

def _csv_path() -> str:
    """Write CSV next to this migration file."""
    return os.path.join(os.path.dirname(__file__), CSV_FILENAME)

def _fetch_all_scalar(conn, sql: str) -> List[str]:
    return [r[0] for r in conn.execute(sa.text(sql)).fetchall()]

def _fetch_reference_data(conn) -> List[str]:
    """Return list of calendar ids."""
    calendars = _fetch_all_scalar(conn, "SELECT id FROM calendars")
    return calendars

def _pick_day_type(d: date) -> str:
    # Weekends are auto-labeled
    if d.weekday() >= 5:
        return "weekend"
    # Weighted choice for weekdays
    r = random.random()
    acc = 0.0
    for label, w in DAY_TYPES:
        acc += w
        if r <= acc:
            return label
    return DAY_TYPES[-1][0]  # fallback

def _generate_rows(calendar_ids: List[str], max_rows: int) -> List[Dict[str, object]]:
    """
    Generate random calendar_day rows that are unique on (calendar_id, date).
    """
    if SEED is not None:
        try:
            random.seed(int(SEED))
        except ValueError:
            random.seed(SEED)

    if not calendar_ids:
        raise RuntimeError("No calendars found. Cannot generate calendar_days.")

    days_span = (END_DATE - START_DATE).days + 1
    theoretical_max = len(calendar_ids) * max(0, days_span)
    target = min(max_rows, theoretical_max)

    unique = set()
    rows: List[Dict[str, object]] = []
    now = datetime.now(timezone.utc)

    log.info("[cal_days] generating rows; calendars=%d, date_range=%s..%s (~%d days), target=%d (cap=%d)",
             len(calendar_ids), START_DATE.isoformat(), END_DATE.isoformat(), days_span, target, theoretical_max)

    # Randomly sample (calendar_id, date) pairs without violating uniqueness
    # We’ll attempt random picks; with high caps, this is fine for test/dev data.
    attempts = 0
    max_attempts = target * 10 if target else 1000

    while len(rows) < target and attempts < max_attempts:
        attempts += 1
        cid = random.choice(calendar_ids)
        d = START_DATE + timedelta(days=random.randint(0, max(0, days_span - 1)))
        key = (cid, d.isoformat())
        if key in unique:
            continue
        unique.add(key)

        day_type = _pick_day_type(d)

        note = random.choice([
            "",
            "Early dismissal",
            "Teacher inservice",
            "District holiday",
            "Adjusted schedule",
            "Testing day",
        ])

        rows.append({
            "id": str(uuid.uuid4()),
            "calendar_id": cid,
            "date": d.isoformat(),
            "day_type": day_type,
            "notes": note,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        })

    if len(rows) < target:
        log.warning("[cal_days] generated %d rows < target=%d (uniqueness/range limits).", len(rows), target)
    else:
        log.info("[cal_days] generated %d rows.", len(rows))

    return rows

def _write_csv(csv_path: str, rows: List[Dict[str, object]]) -> None:
    fieldnames = ["id", "calendar_id", "date", "day_type", "notes", "created_at", "updated_at"]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    log.info("[cal_days] wrote CSV: %s (rows=%d)", csv_path, len(rows))

def _read_csv(csv_path: str) -> List[Dict[str, object]]:
    with open(csv_path, "r", newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        data = list(r)
    log.info("[cal_days] read CSV: %s (rows=%d)", csv_path, len(data))
    return data

# --- Migration ops -------------------------------------------------------------

def upgrade():
    conn = op.get_bind()

    # 1) Ref data
    calendar_ids = _fetch_reference_data(conn)
    log.info("[cal_days] found %d calendar(s).", len(calendar_ids))

    # 2) Generate + write CSV
    rows = _generate_rows(calendar_ids, DEFAULT_ROW_COUNT)
    csv_path = _csv_path()
    _write_csv(csv_path, rows)

    # 3) Clear table (idempotent regeneration)
    log.info("[cal_days] clearing table calendar_days before insert.")
    conn.execute(sa.text("DELETE FROM calendar_days"))

    # 4) Read + bulk insert
    data = _read_csv(csv_path)

    calendar_days = sa.table(
        "calendar_days",
        sa.column("id", sa.String),
        sa.column("calendar_id", sa.String),
        sa.column("date", sa.Date),
        sa.column("day_type", sa.String),
        sa.column("notes", sa.Text),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )

    to_insert = []
    for r in data:
        to_insert.append({
            "id": r["id"],
            "calendar_id": r["calendar_id"],
            "date": datetime.fromisoformat(r["date"]).date(),
            "day_type": r["day_type"] or "instructional",
            "notes": r.get("notes") or None,
            "created_at": datetime.fromisoformat(r["created_at"]),
            "updated_at": datetime.fromisoformat(r["updated_at"]),
        })

    CHUNK = 1000
    for i in range(0, len(to_insert), CHUNK):
        batch = to_insert[i:i+CHUNK]
        op.bulk_insert(calendar_days, batch)
        log.info("[cal_days] inserted chunk %d..%d", i, i + len(batch))

    log.info("[cal_days] finished inserting %d rows into calendar_days.", len(to_insert))

def downgrade():
    conn = op.get_bind()
    log.info("[cal_days] downgrade: clearing calendar_days.")
    conn.execute(sa.text("DELETE FROM calendar_days"))