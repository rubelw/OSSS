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
revision = "0093_seed_behavior_int"
down_revision = "0092_populate_att_evts"  # update if needed
branch_labels = None
depends_on = None

# ---- Logging ---------------------------------------------------------------
log = logging.getLogger("alembic.runtime.migration")

_log_level = os.getenv("MIG_LOG_LEVEL", "").upper()
if _log_level:
    try:
        log.setLevel(getattr(logging, _log_level))
    except Exception:
        pass

# ---- Config ----------------------------------------------------------------
DEFAULT_ROW_COUNT = int(os.getenv("BEHAVIOR_INTERVENTION_ROWS", "600"))
SEED = os.getenv("BEHAVIOR_INTERVENTION_SEED")  # e.g., "42" (deterministic)
END_DATE = date.today()
START_DATE = END_DATE - timedelta(days=270)  # ~last 9 months
CSV_FILENAME = "behavior_interventions.csv"

INTERVENTION_CHOICES = [
    "Check-in/Check-out (CICO)",
    "Behavior contract",
    "Individual counseling",
    "Small-group counseling",
    "Restorative conference",
    "Mentoring",
    "PBIS Tier 2 supports",
    "Functional behavior assessment (FBA)",
    "Behavior intervention plan (BIP)",
    "Parent/guardian meeting",
    "Scheduled movement breaks",
    "Preferential seating",
    "Daily behavior report card",
    "Goal setting & self-monitoring",
    "Social skills coaching",
]


# ---- Helpers ---------------------------------------------------------------
def _csv_path() -> str:
    """Write CSV next to this migration file."""
    return os.path.join(os.path.dirname(__file__), CSV_FILENAME)


def _fetch_all_scalar(conn, sql: str) -> List[str]:
    return [r[0] for r in conn.execute(sa.text(sql)).fetchall()]


def _fetch_reference_data(conn) -> List[str]:
    students = _fetch_all_scalar(conn, "SELECT id FROM students")
    return students


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
    max_rows: int,
) -> List[Dict[str, object]]:
    """
    Generate behavior_interventions rows.
    No uniqueness constraints beyond UUID PK, so we can sample freely.
    """
    if SEED is not None:
        try:
            random.seed(int(SEED))
        except ValueError:
            random.seed(SEED)
        log.info("Random seed set (BEHAVIOR_INTERVENTION_SEED=%r).", SEED)

    if not student_ids:
        raise RuntimeError("No students found. Cannot generate behavior_interventions.")

    span_days = (END_DATE - START_DATE).days
    target = max_rows

    log.info(
        "Generating behavior_interventions: target=%d, date_range=%s..%s, students=%d",
        target, START_DATE.isoformat(), END_DATE.isoformat(), len(student_ids)
    )
    _log_sample("students", student_ids)

    rows: List[Dict[str, object]] = []
    while len(rows) < target:
        sid = random.choice(student_ids)
        start = START_DATE + timedelta(days=random.randint(0, max(0, span_days)))
        # ~60% interventions have an end_date after start; otherwise open-ended (None)
        if random.random() < 0.6:
            # end between 7 and 60 days after start, not past END_DATE
            dur = random.randint(7, 60)
            raw_end = start + timedelta(days=dur)
            end = min(raw_end, END_DATE)
        else:
            end = None

        now = datetime.now(timezone.utc)
        rows.append(
            {
                "id": str(uuid.uuid4()),
                "student_id": sid,
                "intervention": random.choice(INTERVENTION_CHOICES),
                "start_date": start.isoformat(),
                "end_date": end.isoformat() if end else "",
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
        "intervention",
        "start_date",
        "end_date",
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


# ---- Migration -------------------------------------------------------------
def upgrade():
    conn = op.get_bind()
    log.info("---- populate behavior_interventions: START ----")
    log.debug(
        "Config: ROWS=%d, SEED=%r, DATE_RANGE=%s..%s, CSV=%s",
        DEFAULT_ROW_COUNT, SEED, START_DATE.isoformat(), END_DATE.isoformat(), _csv_path()
    )

    try:
        # 1) Reference data
        student_ids = _fetch_reference_data(conn)
        log.info("Refs loaded: students=%d", len(student_ids))

        # 2) Generate + write CSV (always rewrite)
        rows = _generate_rows(student_ids, DEFAULT_ROW_COUNT)
        csv_path = _csv_path()
        _write_csv(csv_path, rows)

        # 3) Clear table for idempotency
        log.info("Clearing behavior_interventions table...")
        res = conn.execute(sa.text("DELETE FROM behavior_interventions"))
        try:
            log.info("Deleted %s existing rows.", f"{res.rowcount:,}")
        except Exception:
            log.debug("Rowcount not available for DELETE.")

        # 4) Read CSV and bulk insert
        data = _read_csv(csv_path)

        behavior_interventions = sa.table(
            "behavior_interventions",
            sa.column("id", sa.String),
            sa.column("student_id", sa.String),
            sa.column("intervention", sa.Text),
            sa.column("start_date", sa.Date),
            sa.column("end_date", sa.Date),
            sa.column("created_at", sa.DateTime(timezone=True)),
            sa.column("updated_at", sa.DateTime(timezone=True)),
        )

        to_insert = []
        for r in data:
            to_insert.append(
                {
                    "id": r["id"],
                    "student_id": r["student_id"],
                    "intervention": r["intervention"],
                    "start_date": datetime.fromisoformat(r["start_date"]).date(),
                    "end_date": (
                        datetime.fromisoformat(r["end_date"]).date()
                        if str(r.get("end_date") or "").strip()
                        else None
                    ),
                    "created_at": datetime.fromisoformat(r["created_at"]),
                    "updated_at": datetime.fromisoformat(r["updated_at"]),
                }
            )

        total = len(to_insert)
        log.info("Inserting %d rows into behavior_interventions (chunked)...", total)
        CHUNK = 1000
        for i in range(0, total, CHUNK):
            op.bulk_insert(behavior_interventions, to_insert[i : i + CHUNK])
            log.debug("Inserted rows %d..%d", i + 1, min(i + CHUNK, total))

        log.info("---- populate behavior_interventions: DONE (inserted %d rows) ----", total)

    except Exception as e:
        log.exception("Migration failed: %s", e)
        raise


def downgrade():
    log.info("---- populate behavior_interventions: DOWNGRADE (clear table) ----")
    conn = op.get_bind()
    try:
        res = conn.execute(sa.text("DELETE FROM behavior_interventions"))
        try:
            log.info("Deleted %s rows.", f"{res.rowcount:,}")
        except Exception:
            log.debug("Rowcount not available for DELETE.")
    except Exception as e:
        log.exception("Downgrade failed: %s", e)
        raise