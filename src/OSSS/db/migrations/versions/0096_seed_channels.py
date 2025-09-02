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
revision = "0096_seed_channels"
down_revision = "0095_seed_calendar_dy"  # update if needed
branch_labels = None
depends_on = None

# ---- Logging ---------------------------------------------------------------
log = logging.getLogger("alembic.runtime.migration")


# --- Config knobs --------------------------------------------------------------
CSV_FILENAME = "channels.csv"

# How many channels to generate (cap will be applied by uniqueness)
DEFAULT_ROW_COUNT = int(os.getenv("CHANNEL_ROWS", "18"))

# RNG seed for reproducible runs (unset → true randomness)
SEED = os.getenv("CHANNEL_SEED")  # e.g. "42"

# Which organization to seed against
ORG_CODE = os.getenv("CHANNELS_ORG_CODE", "05400000")

# Audience mix
AUDIENCE_CHOICES = ["public", "staff", "board"]
AUDIENCE_WEIGHTS = [0.72, 0.20, 0.08]  # must align with choices above

# ------------------------------------------------------------------------------

def _csv_path() -> str:
    """CSV is written next to this migration file."""
    return os.path.join(os.path.dirname(__file__), CSV_FILENAME)

def _fetch_all_scalar(conn, sql: str) -> List[str]:
    return [r[0] for r in conn.execute(sa.text(sql)).fetchall()]

def _fetch_org_id_by_code(conn, code: str) -> str:
    row = conn.execute(
        sa.text("SELECT id FROM organizations WHERE code = :code"),
        {"code": code},
    ).fetchone()
    if not row:
        raise RuntimeError(
            f"No organization found with code={code!r}. Cannot populate channels."
        )
    return row[0]

def _generate_channel_names(n: int) -> List[str]:
    """Create n unique-ish channel names."""
    base = [
        "District News",
        "Announcements",
        "Events",
        "Board Updates",
        "Staff Updates",
        "Transportation",
        "Facilities",
        "Health & Safety",
        "Technology",
        "Community",
        "Athletics",
        "Clubs",
        "Library",
        "Arts",
        "Music",
        "Theater",
        "Superintendent",
        "Principals",
        "Curriculum",
        "Special Education",
        "Food Services",
        "Counseling",
        "Family Portal",
    ]
    names: List[str] = []

    # Start with the base list (trim/pad to target)
    pool = list(base)
    # If we need more, synthesize with numeric suffixes
    i = 1
    while len(pool) < n:
        pool.append(f"Channel {i}")
        i += 1

    # Shuffle and take first n, ensure uniqueness
    random.shuffle(pool)
    for name in pool[:n]:
        names.append(name)

    # If for some reason duplicates slipped in, de-dupe with suffixes
    seen = set()
    unique: List[str] = []
    for nm in names:
        if nm not in seen:
            seen.add(nm)
            unique.append(nm)
        else:
            k = 2
            while f"{nm} #{k}" in seen:
                k += 1
            alt = f"{nm} #{k}"
            seen.add(alt)
            unique.append(alt)

    return unique

def _generate_rows(org_id: str, max_rows: int) -> List[Dict[str, object]]:
    if SEED is not None:
        try:
            random.seed(int(SEED))
        except ValueError:
            random.seed(SEED)

    target = max(1, int(max_rows))
    names = _generate_channel_names(target)

    desc_options = [
        "",
        "Official updates and news for the district.",
        "Information for staff and internal announcements.",
        "Updates from the school board.",
        "Upcoming events and activities.",
        "Transportation notices and route updates.",
        "Technology tips and service notices.",
        "Community engagement and partnerships.",
        "Arts, music, and theater highlights.",
        "Health and safety reminders.",
    ]

    rows: List[Dict[str, object]] = []
    for nm in names:
        audience = random.choices(AUDIENCE_CHOICES, weights=AUDIENCE_WEIGHTS, k=1)[0]
        rows.append(
            {
                "id": str(uuid.uuid4()),
                "org_id": org_id,
                "name": nm,
                "audience": audience,
                "description": random.choice(desc_options),
            }
        )

    log.info("[channels] generated %d rows for org_id=%s", len(rows), org_id)
    return rows

def _write_csv(csv_path: str, rows: List[Dict[str, object]]) -> None:
    fieldnames = ["id", "org_id", "name", "audience", "description"]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    log.info("[channels] wrote CSV: %s (rows=%d)", csv_path, len(rows))

def _read_csv(csv_path: str) -> List[Dict[str, object]]:
    with open(csv_path, "r", newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        data = list(r)
    log.info("[channels] read CSV: %s (rows=%d)", csv_path, len(data))
    return data

# --- Migration ops -------------------------------------------------------------

def upgrade():
    conn = op.get_bind()

    # 1) Locate target organization
    org_id = _fetch_org_id_by_code(conn, ORG_CODE)
    log.info("[channels] using organization (code=%s) id=%s", ORG_CODE, org_id)

    # 2) Generate + write CSV
    rows = _generate_rows(org_id, DEFAULT_ROW_COUNT)
    csv_path = _csv_path()
    _write_csv(csv_path, rows)

    # 3) Clear table for idempotent regeneration
    log.info("[channels] clearing table channels before insert.")
    conn.execute(sa.text("DELETE FROM channels"))

    # 4) Read CSV and bulk insert
    data = _read_csv(csv_path)

    channels = sa.table(
        "channels",
        sa.column("id", sa.String),
        sa.column("org_id", sa.String),
        sa.column("name", sa.String),
        sa.column("audience", sa.String),
        sa.column("description", sa.Text),
    )

    # Prepare rows (CSV is already typed as strings)
    to_insert = []
    for r in data:
        to_insert.append(
            {
                "id": r["id"],
                "org_id": r["org_id"],
                "name": r["name"],
                "audience": r["audience"],
                "description": (r.get("description") or None),
            }
        )

    CHUNK = 1000
    total = len(to_insert)
    for i in range(0, total, CHUNK):
        batch = to_insert[i : i + CHUNK]
        op.bulk_insert(channels, batch)
        log.info("[channels] inserted chunk %d..%d", i, i + len(batch))

    log.info("[channels] finished inserting %d rows into channels.", total)

def downgrade():
    conn = op.get_bind()
    log.info("[channels] downgrade: clearing channels.")
    conn.execute(sa.text("DELETE FROM channels"))