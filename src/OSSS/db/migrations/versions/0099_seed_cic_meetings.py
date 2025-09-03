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
revision = "0099_seed_cic_meetings"
down_revision = "0098_seed_cic_comm"  # update if needed
branch_labels = None
depends_on = None

# ---- Logging ---------------------------------------------------------------
log = logging.getLogger("alembic.runtime.migration")


# ---- Config ----
CSV_FILENAME = "cic_meetings.csv"
DEFAULT_ROW_COUNT = int(os.getenv("CIC_MEETING_ROWS", "40"))
SEED = os.getenv("CIC_MEETING_SEED")  # e.g. "42"

def _csv_path() -> str:
    """Write/read CSV next to this migration file."""
    return os.path.join(os.path.dirname(__file__), CSV_FILENAME)

def _fetch_all_scalar(conn, sql: str, **params) -> List[str]:
    return [r[0] for r in conn.execute(sa.text(sql), params).fetchall()]

def _fetch_committees(conn) -> List[str]:
    ids = _fetch_all_scalar(conn, "SELECT id FROM cic_committees")
    if not ids:
        raise RuntimeError("No cic_committees found. Seed committees before meetings.")
    return ids

def _generate_rows(committee_ids: List[str], n: int) -> List[Dict[str, object]]:
    """
    Generate meeting rows tied to existing committees.
    scheduled_at around today ± 60 days. ends_at 60–180 minutes after start.
    """
    if SEED is not None:
        try:
            random.seed(int(SEED))
        except ValueError:
            random.seed(SEED)

    titles = [
        "Regular Meeting",
        "Special Meeting",
        "Planning Session",
        "Work Session",
        "Public Hearing",
        "Annual Review",
        "Budget Workshop",
        "Policy Discussion",
        "Stakeholder Forum",
        "Orientation",
    ]
    locations = [
        "District Office, Board Room",
        "Main Campus, Library",
        "High School, Room 201",
        "Middle School, Auditorium",
        "Elementary Campus, MPR",
        "Virtual (Video Conference)",
    ]
    statuses = ["scheduled", "completed", "cancelled", "postponed"]

    rows: List[Dict[str, object]] = []
    now = datetime.now(timezone.utc)

    for i in range(n):
        cid = random.choice(committee_ids)

        # pick a start within ±60 days of today, at a “meeting-ish” hour
        day_offset = random.randint(-60, 60)
        hour = random.choice([8, 9, 15, 16, 17, 18, 19])
        minute = random.choice([0, 15, 30, 45])
        scheduled_at = (now + timedelta(days=day_offset)).replace(
            hour=hour, minute=minute, second=0, microsecond=0
        )

        duration_min = random.choice([60, 75, 90, 120, 150, 180])
        ends_at = scheduled_at + timedelta(minutes=duration_min)

        title = random.choice(titles)
        # Add a tiny suffix sometimes for variety
        if random.random() < 0.25:
            title = f"{title} #{random.randint(2, 12)}"

        status = random.choices(statuses, weights=[7, 2, 0.5, 0.5], k=1)[0]
        is_public = random.random() < 0.8  # most meetings public

        rows.append(
            {
                "id": str(uuid.uuid4()),
                "committee_id": cid,
                "title": title,
                "scheduled_at": scheduled_at.isoformat(),
                "ends_at": ends_at.isoformat(),
                "location": random.choice(locations),
                "status": status,
                "is_public": "true" if is_public else "false",  # write as str in CSV
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
            }
        )

    return rows

def _write_csv(path: str, rows: List[Dict[str, object]]) -> None:
    fieldnames = [
        "id",
        "committee_id",
        "title",
        "scheduled_at",
        "ends_at",
        "location",
        "status",
        "is_public",
        "created_at",
        "updated_at",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)

def _read_csv(path: str) -> List[Dict[str, object]]:
    with open(path, "r", newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        return list(r)

def _to_bool(v: object) -> bool:
    if isinstance(v, bool):
        return v
    s = (v or "").strip().lower()
    return s in {"1", "true", "t", "yes", "y"}

def upgrade():
    conn = op.get_bind()

    log.info("[cic_meetings] begin population; target rows=%s", DEFAULT_ROW_COUNT)

    # 1) Reference data
    committee_ids = _fetch_committees(conn)
    log.info("[cic_meetings] found %d committee(s) for linking", len(committee_ids))

    # 2) Generate & write CSV
    rows = _generate_rows(committee_ids, DEFAULT_ROW_COUNT)
    csv_path = _csv_path()
    _write_csv(csv_path, rows)
    log.info("[cic_meetings] wrote CSV: %s (rows=%d)", csv_path, len(rows))

    # 3) Clear table idempotently
    conn.execute(sa.text("DELETE FROM cic_meetings"))
    log.info("[cic_meetings] table cleared")

    # 4) Read CSV and prepare inserts
    data = _read_csv(csv_path)
    log.info("[cic_meetings] read CSV rows=%d", len(data))

    cic_meetings = sa.table(
        "cic_meetings",
        sa.column("id", sa.String),
        sa.column("committee_id", sa.String),
        sa.column("title", sa.Text),
        sa.column("scheduled_at", sa.DateTime(timezone=True)),
        sa.column("ends_at", sa.DateTime(timezone=True)),
        sa.column("location", sa.Text),
        sa.column("status", sa.Text),
        sa.column("is_public", sa.Boolean),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )

    to_insert: List[Dict[str, object]] = []
    for r in data:
        sched = datetime.fromisoformat(r["scheduled_at"])
        ends = datetime.fromisoformat(r["ends_at"]) if (r.get("ends_at") or "").strip() else None
        to_insert.append(
            {
                "id": r["id"],
                "committee_id": r["committee_id"],
                "title": r["title"],
                "scheduled_at": sched,
                "ends_at": ends,
                "location": r.get("location") or None,
                "status": r.get("status") or "scheduled",
                "is_public": _to_bool(r.get("is_public")),
                "created_at": datetime.fromisoformat(r["created_at"]),
                "updated_at": datetime.fromisoformat(r["updated_at"]),
            }
        )

    CHUNK = 1000
    total = 0
    for i in range(0, len(to_insert), CHUNK):
        batch = to_insert[i : i + CHUNK]
        op.bulk_insert(cic_meetings, batch)
        total += len(batch)
        log.info("[cic_meetings] inserted batch %d..%d (batch=%d)", i + 1, i + len(batch), len(batch))

    log.info("[cic_meetings] complete; inserted=%d", total)

def downgrade():
    conn = op.get_bind()
    conn.execute(sa.text("DELETE FROM cic_meetings"))
    log.info("[cic_meetings] downgraded; table cleared (CSV left on disk)")
