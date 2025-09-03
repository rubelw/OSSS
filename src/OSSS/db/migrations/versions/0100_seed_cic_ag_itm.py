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
revision = "0100_seed_cic_ag_itm"
down_revision = "0099_seed_cic_meetings"  # update if needed
branch_labels = None
depends_on = None

# ---- Logging ---------------------------------------------------------------
log = logging.getLogger("alembic.runtime.migration")


CSV_FILENAME = "cic_agenda_items.csv"

# ---- Tuning / env ----
SEED = os.getenv("CIC_AGENDA_ITEMS_SEED")           # e.g., "42" for determinism
MIN_ITEMS_PER_MEETING = int(os.getenv("CIC_AGENDA_MIN_PER", "3"))
MAX_ITEMS_PER_MEETING = int(os.getenv("CIC_AGENDA_MAX_PER", "8"))
PARENT_PROB = float(os.getenv("CIC_AGENDA_PARENT_PROB", "0.30"))  # 30% of non-first items get a parent
TIME_ALLOC_CHOICES = [None, 5, 10, 15, 20, 30, 45, 60]


def _csv_path() -> str:
    return os.path.join(os.path.dirname(__file__), CSV_FILENAME)


def _fetch_all_scalar(conn, sql: str) -> List[str]:
    return [r[0] for r in conn.execute(sa.text(sql)).fetchall()]


def _fetch_reference_data(conn):
    meeting_ids = _fetch_all_scalar(conn, "SELECT id FROM cic_meetings")
    subject_ids = _fetch_all_scalar(conn, "SELECT id FROM subjects")
    course_ids  = _fetch_all_scalar(conn, "SELECT id FROM courses")
    return meeting_ids, subject_ids, course_ids


def _generate_rows(
    meeting_ids: List[str],
    subject_ids: List[str],
    course_ids: List[str],
    min_per: int,
    max_per: int,
) -> List[Dict[str, object]]:
    """
    Generate agenda items per meeting with unique (meeting_id, position).
    Some items will be nested (parent/child) and some may reference a subject/course.
    """
    if SEED is not None:
        try:
            random.seed(int(SEED))
        except ValueError:
            random.seed(SEED)

    if not meeting_ids:
        raise RuntimeError("No cic_meetings found. Seed meetings before agenda items.")
    if not subject_ids:
        raise RuntimeError("No subjects found. Seed subjects before agenda items.")
    if not course_ids:
        raise RuntimeError("No courses found. Seed courses before agenda items.")

    now = datetime.now(timezone.utc)
    rows: List[Dict[str, object]] = []

    for mid in meeting_ids:
        count = random.randint(max(1, min_per), max(min_per, max_per))
        # keep track of created ids for this meeting so parent_id can reference earlier ones
        created_ids: List[str] = []
        for pos in range(1, count + 1):
            _id = str(uuid.uuid4())

            parent_id: Optional[str] = None
            if created_ids and random.random() < PARENT_PROB:
                parent_id = random.choice(created_ids)

            title = random.choice(
                [
                    "Opening Remarks",
                    "Curriculum Review",
                    "Assessment Alignment",
                    "Policy Discussion",
                    "Community Input",
                    "Instructional Materials",
                    "Program Update",
                    "New Business",
                    "Old Business",
                    "Action Items",
                ]
            )

            desc = random.choice(
                [
                    "",
                    "Discussion led by chair.",
                    "Presentation from staff.",
                    "Review supporting documents.",
                    "Public comment period included.",
                    "Follow-up from previous meeting.",
                ]
            )

            tmins = random.choice(TIME_ALLOC_CHOICES)

            # Always pull valid FKs from given tables
            subj_id = random.choice(subject_ids)
            crs_id  = random.choice(course_ids)

            rows.append(
                {
                    "id": _id,
                    "meeting_id": mid,
                    "parent_id": parent_id or "",
                    "position": pos,
                    "title": f"{title} #{pos}",
                    "description": desc,
                    "time_allocated_minutes": "" if tmins is None else tmins,
                    "subject_id": subj_id,
                    "course_id": crs_id,
                    "created_at": now.isoformat(),
                    "updated_at": now.isoformat(),
                }
            )
            created_ids.append(_id)

    log.info("[cic_agenda_items] generated %d rows across %d meetings", len(rows), len(meeting_ids))
    return rows


def _write_csv(csv_path: str, rows: List[Dict[str, object]]) -> None:
    fieldnames = [
        "id",
        "meeting_id",
        "parent_id",
        "position",
        "title",
        "description",
        "time_allocated_minutes",
        "subject_id",
        "course_id",
        "created_at",
        "updated_at",
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    log.info("[cic_agenda_items] wrote CSV: %s (rows=%d)", csv_path, len(rows))


def _read_csv(csv_path: str) -> List[Dict[str, object]]:
    with open(csv_path, "r", newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        data = list(r)
    log.info("[cic_agenda_items] read CSV: %s (rows=%d)", csv_path, len(data))
    return data


def upgrade():
    conn = op.get_bind()

    # 1) Reference data
    meeting_ids, subject_ids, course_ids = _fetch_reference_data(conn)
    log.info(
        "[cic_agenda_items] refs: meetings=%d, subjects=%d, courses=%d",
        len(meeting_ids), len(subject_ids), len(course_ids)
    )

    # 2) Generate & write CSV
    rows = _generate_rows(meeting_ids, subject_ids, course_ids, MIN_ITEMS_PER_MEETING, MAX_ITEMS_PER_MEETING)
    csv_path = _csv_path()
    _write_csv(csv_path, rows)

    # 3) Idempotent: clear existing
    log.info("[cic_agenda_items] clearing table before insert")
    conn.execute(sa.text("DELETE FROM cic_agenda_items"))

    # 4) Load CSV and bulk insert
    data = _read_csv(csv_path)

    table = sa.table(
        "cic_agenda_items",
        sa.column("id", sa.String),
        sa.column("meeting_id", sa.String),
        sa.column("parent_id", sa.String),
        sa.column("position", sa.Integer),
        sa.column("title", sa.Text),
        sa.column("description", sa.Text),
        sa.column("time_allocated_minutes", sa.Integer),
        sa.column("subject_id", sa.String),
        sa.column("course_id", sa.String),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )

    to_insert = []
    for r in data:
        to_insert.append(
            {
                "id": r["id"],
                "meeting_id": r["meeting_id"],
                "parent_id": r["parent_id"] or None,
                "position": int(r["position"]),
                "title": r["title"],
                "description": r.get("description") or None,
                "time_allocated_minutes": int(r["time_allocated_minutes"]) if (r.get("time_allocated_minutes") or "").strip() != "" else None,
                "subject_id": r["subject_id"],
                "course_id": r["course_id"],
                "created_at": datetime.fromisoformat(r["created_at"]),
                "updated_at": datetime.fromisoformat(r["updated_at"]),
            }
        )

    CHUNK = 1000
    for i in range(0, len(to_insert), CHUNK):
        op.bulk_insert(table, to_insert[i : i + CHUNK])
    log.info("[cic_agenda_items] inserted %d rows (chunk=%d)", len(to_insert), CHUNK)


def downgrade():
    conn = op.get_bind()
    conn.execute(sa.text("DELETE FROM cic_agenda_items"))
    log.info("[cic_agenda_items] table cleared (downgrade)")