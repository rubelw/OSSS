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
revision = "0092_populate_att_evts"
down_revision = "0091_populate_immuniztns"  # update if needed
branch_labels = None
depends_on = None

# ---- Logging ---------------------------------------------------------------
log = logging.getLogger("alembic.runtime.migration")
# allow raising verbosity via env: MIG_LOG_LEVEL=DEBUG alembic upgrade head
_log_level = os.getenv("MIG_LOG_LEVEL", "").upper()
if _log_level:
    try:
        log.setLevel(getattr(logging, _log_level))
    except Exception:
        pass

# --- Config ----------------------------------------------------------------
DEFAULT_ROW_COUNT = int(os.getenv("ATTENDANCE_EVENT_ROWS", "1200"))
SEED = os.getenv("ATTENDANCE_EVENT_SEED")  # e.g. "42" (deterministic)
END_DATE = date.today()
START_DATE = END_DATE - timedelta(days=180)  # last ~6 months
CSV_FILENAME = "attendance_events.csv"


# --- Utils -----------------------------------------------------------------
def _csv_path() -> str:
    """Write CSV next to this migration file."""
    return os.path.join(os.path.dirname(__file__), CSV_FILENAME)


def _fetch_all_scalar(conn, sql: str) -> List[str]:
    return [r[0] for r in conn.execute(sa.text(sql)).fetchall()]


def _fetch_reference_data(conn) -> Tuple[List[str], List[str], List[str]]:
    student_ids = _fetch_all_scalar(conn, "SELECT id FROM students")
    meeting_ids = _fetch_all_scalar(conn, "SELECT id FROM section_meetings")
    codes       = _fetch_all_scalar(conn, "SELECT code FROM attendance_codes")
    return student_ids, meeting_ids, codes


def _log_sample(name: str, seq: List[str], max_items: int = 3) -> None:
    if not seq:
        log.debug("%s sample: []", name)
        return
    sample = seq[:max_items]
    more = max(0, len(seq) - len(sample))
    if more:
        log.debug("%s sample (%d of %d): %s, ... (+%d more)",
                  name, len(sample), len(seq), sample, more)
    else:
        log.debug("%s sample (%d): %s", name, len(sample), sample)


def _generate_rows(
    student_ids: List[str],
    meeting_ids: List[str],
    codes: List[str],
    max_rows: int,
) -> List[Dict[str, object]]:
    """
    Generate random, unique attendance rows consistent with FK + unique constraint.
    Unique key: (student_id, date, section_meeting_id).
    """
    if SEED is not None:
        try:
            random.seed(int(SEED))
        except ValueError:
            random.seed(SEED)
        log.info("Random seed set (ATTENDANCE_EVENT_SEED=%r).", SEED)

    if not student_ids:
        raise RuntimeError("No students found. Cannot generate attendance_events.")
    if not meeting_ids:
        raise RuntimeError("No section_meetings found. Cannot generate attendance_events.")
    if not codes:
        raise RuntimeError("No attendance_codes found. Cannot generate attendance_events.")

    log.info(
        "Generating attendance_events: target=%d, date_range=%s..%s, students=%d, meetings=%d, codes=%d",
        max_rows, START_DATE.isoformat(), END_DATE.isoformat(),
        len(student_ids), len(meeting_ids), len(codes),
    )
    _log_sample("students", student_ids)
    _log_sample("section_meetings", meeting_ids)
    _log_sample("codes", codes)

    unique = set()
    rows: List[Dict[str, object]] = []

    span_days = (END_DATE - START_DATE).days
    theoretical_max = len(student_ids) * len(meeting_ids) * max(1, span_days + 1)
    target = min(max_rows, theoretical_max)
    if target < max_rows:
        log.warning("Requested %d rows but theoretical max is %d; capping to %d.",
                    max_rows, theoretical_max, target)

    minutes_choices = [None, 0, 5, 10, 15, 30, 45, 60]

    while len(rows) < target:
        sid = random.choice(student_ids)
        mid = random.choice(meeting_ids)
        d = START_DATE + timedelta(days=random.randint(0, max(0, span_days)))
        key = (sid, d.isoformat(), mid)
        if key in unique:
            continue
        unique.add(key)

        code = random.choice(codes)
        mins = random.choice(minutes_choices)
        note = random.choice(
            ["", "Verified by office", "Parent called", "Tardy due to bus delay",
             "Excused absence", "Left early for appointment"]
        )
        now = datetime.now(timezone.utc)

        rows.append(
            {
                "id": str(uuid.uuid4()),
                "student_id": sid,
                "section_meeting_id": mid,
                "date": d.isoformat(),
                "code": code,
                "minutes": mins if mins is not None else "",
                "notes": note,
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
            }
        )

        if len(rows) % 10000 == 0:
            log.info("Generated %d rows...", len(rows))

    log.info("Finished generating %d rows.", len(rows))
    return rows


def _write_csv(csv_path: str, rows: List[Dict[str, object]]) -> None:
    fieldnames = [
        "id",
        "student_id",
        "section_meeting_id",
        "date",
        "code",
        "minutes",
        "notes",
        "created_at",
        "updated_at",
    ]
    log.info("Writing CSV: %s", csv_path)
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    try:
        size = os.path.getsize(csv_path)
        log.info("CSV written (%s bytes).", f"{size:,}")
    except Exception:
        pass


def _read_csv(csv_path: str) -> List[Dict[str, object]]:
    log.info("Reading CSV: %s", csv_path)
    with open(csv_path, "r", newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        data = list(r)
    log.info("Read %d CSV rows.", len(data))
    return data


# --- Migration --------------------------------------------------------------
def upgrade():
    conn = op.get_bind()
    log.info("---- populate attendance_events: START ----")
    log.debug(
        "Config: ROWS=%d, SEED=%r, DATE_RANGE=%s..%s, CSV=%s",
        DEFAULT_ROW_COUNT, SEED, START_DATE.isoformat(), END_DATE.isoformat(), _csv_path()
    )

    try:
        # 1) Reference data
        student_ids, meeting_ids, codes = _fetch_reference_data(conn)
        log.info("Refs loaded: students=%d, section_meetings=%d, codes=%d",
                 len(student_ids), len(meeting_ids), len(codes))

        # 2) Generate + write CSV
        rows = _generate_rows(student_ids, meeting_ids, codes, DEFAULT_ROW_COUNT)
        csv_path = _csv_path()
        _write_csv(csv_path, rows)

        # 3) Clear table for idempotency
        log.info("Clearing attendance_events table...")
        res = conn.execute(sa.text("DELETE FROM attendance_events"))
        try:
            log.info("Deleted %s existing rows.", f"{res.rowcount:,}")
        except Exception:
            log.debug("Rowcount not available for DELETE.")

        # 4) Read CSV and bulk insert
        data = _read_csv(csv_path)

        attendance_events = sa.table(
            "attendance_events",
            sa.column("id", sa.String),
            sa.column("student_id", sa.String),
            sa.column("section_meeting_id", sa.String),
            sa.column("date", sa.Date),
            sa.column("code", sa.String),
            sa.column("minutes", sa.Integer),
            sa.column("notes", sa.Text),
            sa.column("created_at", sa.DateTime(timezone=True)),
            sa.column("updated_at", sa.DateTime(timezone=True)),
        )

        to_insert = []
        for r in data:
            to_insert.append(
                {
                    "id": r["id"],
                    "student_id": r["student_id"],
                    "section_meeting_id": r["section_meeting_id"],
                    "date": datetime.fromisoformat(r["date"]).date(),
                    "code": r["code"],
                    "minutes": int(r["minutes"]) if str(r.get("minutes") or "").strip() != "" else None,
                    "notes": r.get("notes") or None,
                    "created_at": datetime.fromisoformat(r["created_at"]),
                    "updated_at": datetime.fromisoformat(r["updated_at"]),
                }
            )

        total = len(to_insert)
        log.info("Inserting %d rows into attendance_events (chunked)...", total)
        CHUNK = 1000
        for i in range(0, total, CHUNK):
            chunk = to_insert[i : i + CHUNK]
            op.bulk_insert(attendance_events, chunk)
            log.debug("Inserted rows %d..%d", i + 1, min(i + CHUNK, total))

        log.info("---- populate attendance_events: DONE (inserted %d rows) ----", total)

    except Exception as e:
        log.exception("Migration failed: %s", e)
        raise


def downgrade():
    log.info("---- populate attendance_events: DOWNGRADE (clear table) ----")
    conn = op.get_bind()
    try:
        res = conn.execute(sa.text("DELETE FROM attendance_events"))
        try:
            log.info("Deleted %s rows.", f"{res.rowcount:,}")
        except Exception:
            log.debug("Rowcount not available for DELETE.")
    except Exception as e:
        log.exception("Downgrade failed: %s", e)
        raise
