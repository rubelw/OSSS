# src/OSSS/db/migrations/versions/0081_populate_audit_logs.py
from __future__ import annotations

import os, csv, json, logging, uuid, random
from pathlib import Path
from contextlib import nullcontext
from typing import Optional
from datetime import date, timedelta


from alembic import op
import sqlalchemy as sa

# ---- Alembic identifiers ----
revision = "0087_populate_att_day_sum"
down_revision = "0086_populate_attendance"  # update if needed
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")


# ---- Config / env toggles ----------------------------------------------------
LOG_LVL        = os.getenv("ADS_LOG_LEVEL", "INFO").upper()
LOG_SQL        = os.getenv("ADS_LOG_SQL", "1") == "1"
LOG_ROWS       = os.getenv("ADS_LOG_ROWS", "1") == "1"
ABORT_IF_ZERO  = os.getenv("ADS_ABORT_IF_ZERO", "1") == "1"

CSV_ENV        = "ADS_CSV_PATH"
CSV_NAME       = "attendance_daily_summary.csv"

# how many sequential days per student to seed
ADS_DAYS_PER_STUDENT = int(os.getenv("ADS_DAYS_PER_STUDENT", "2"))

# start date (YYYY-MM-DD). Defaults to today() if not provided.
ADS_START_DATE = os.getenv("ADS_START_DATE")  # e.g., "2024-09-01"

# minutes defaults / randomization
ADS_PRESENT_DEFAULT = int(os.getenv("ADS_PRESENT_DEFAULT", "360"))
ADS_ABSENT_DEFAULT  = int(os.getenv("ADS_ABSENT_DEFAULT", "0"))
ADS_TARDY_DEFAULT   = int(os.getenv("ADS_TARDY_DEFAULT", "0"))
ADS_RANDOMIZE       = os.getenv("ADS_RANDOMIZE", "0") == "1"
ADS_SEED            = os.getenv("ADS_SEED")

# ---- Table names -------------------------------------------------------------
ADS_TBL      = "attendance_daily_summary"
STUDENTS_TBL = "students"

# ---- Logging setup -----------------------------------------------------------
logging.getLogger("alembic.runtime.migration").setLevel(getattr(logging, LOG_LVL, logging.INFO))
_engine_logger = logging.getLogger("sqlalchemy.engine")
_engine_logger.setLevel(logging.INFO if LOG_SQL else getattr(logging, LOG_LVL, logging.INFO))


# ---- Helpers ----------------------------------------------------------------
def _outer_tx(conn):
    """Open a transaction only if one isn't already active (plays nice with env.py)."""
    try:
        if hasattr(conn, "get_transaction") and conn.get_transaction() is not None:
            return nullcontext()
        if hasattr(conn, "in_transaction") and conn.in_transaction():
            return nullcontext()
    except Exception:
        return nullcontext()
    return conn.begin()


def _default_output_path(name: str) -> Path:
    envp = os.getenv(CSV_ENV)
    if envp:
        p = Path(envp)
        return (p / name) if p.is_dir() else p
    return Path(__file__).resolve().with_name(name)


def _ensure_schema(bind):
    """Ensure uq_attendance_daily(student_id, date) exists for ON CONFLICT usage."""
    insp = sa.inspect(bind)
    if not insp.has_table(ADS_TBL):
        return
    uqs = {u["name"]: u for u in insp.get_unique_constraints(ADS_TBL)}
    expected_cols = ["student_id", "date"]
    if "uq_attendance_daily" in uqs:
        if uqs["uq_attendance_daily"]["column_names"] != expected_cols:
            op.drop_constraint("uq_attendance_daily", ADS_TBL, type_="unique")
            try:
                op.create_unique_constraint("uq_attendance_daily", ADS_TBL, expected_cols)
            except Exception:
                pass
    else:
        try:
            op.create_unique_constraint("uq_attendance_daily", ADS_TBL, expected_cols)
        except Exception:
            pass


def _coerce_start_date() -> date:
    if ADS_START_DATE:
        try:
            y, m, d = [int(x) for x in ADS_START_DATE.split("-")]
            return date(y, m, d)
        except Exception:
            log.warning("[%s] Invalid ADS_START_DATE=%r; defaulting to today()", revision, ADS_START_DATE)
    return date.today()


def _write_csv(bind) -> tuple[Path, int]:
    """
    (Re)generate attendance_daily_summary.csv from current students.
    Returns (path, number_of_rows_written).
    """
    out = _default_output_path(CSV_NAME)
    out.parent.mkdir(parents=True, exist_ok=True)

    insp = sa.inspect(bind)
    have_students = insp.has_table(STUDENTS_TBL)

    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        # 'id' omitted (server default on UUIDMixin). created_at/updated_at omitted (DB defaults).
        w.writerow(["student_id", "date", "present_minutes", "absent_minutes", "tardy_minutes"])

        if not have_students:
            log.warning("[%s] Missing %s; wrote header-only CSV: %s", revision, STUDENTS_TBL, out)
            return out, 0

        rows_q = bind.execute(sa.text(f"SELECT id FROM {STUDENTS_TBL} ORDER BY id")).fetchall()
        student_ids = [str(r[0]) for r in rows_q]
        log.info("[%s] Found students=%d", revision, len(student_ids))

        if not student_ids or ADS_DAYS_PER_STUDENT <= 0:
            log.info("[%s] Nothing to seed (students=%d, days_per_student=%d); header-only CSV: %s",
                     revision, len(student_ids), ADS_DAYS_PER_STUDENT, out)
            return out, 0

        rng = random.Random(ADS_SEED)
        start = _coerce_start_date()
        total_rows = 0

        for sid in student_ids:
            for offset in range(ADS_DAYS_PER_STUDENT):
                dt = start - timedelta(days=offset)

                if ADS_RANDOMIZE:
                    # Simple randomized bucket: present 0–420, absent and tardy small spillovers
                    pm = max(0, min(420, rng.randint(240, 420)))
                    am = 0 if rng.random() < 0.8 else rng.randint(30, 420 - pm)
                    tm = 0 if rng.random() < 0.7 else rng.randint(5, 45)
                else:
                    pm = ADS_PRESENT_DEFAULT
                    am = ADS_ABSENT_DEFAULT
                    tm = ADS_TARDY_DEFAULT

                w.writerow([sid, dt.isoformat(), pm, am, tm])
                total_rows += 1

    log.info("[%s] CSV generated with %d rows => %s", revision, total_rows, out)
    return out, total_rows


def _open_csv(csv_path: Path):
    f = csv_path.open("r", encoding="utf-8", newline="")
    reader = csv.DictReader(f)
    try:
        from itertools import islice
        sample = list(islice(reader, 5))
        log.info("[%s] CSV headers: %s; first rows: %s", revision, reader.fieldnames, sample)
        f.seek(0); next(reader)  # rewind to first data row
    except Exception:
        pass
    return reader, f


def _insert_sql(bind):
    """
    Build INSERT for attendance_daily_summary. If unique (student_id, date) exists,
    use ON CONFLICT DO NOTHING; otherwise use SELECT … WHERE NOT EXISTS guard.
    """
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns(ADS_TBL)}

    ins_cols, vals = [], []

    def add(col: str, param: Optional[str] = None):
        if col in cols:
            ins_cols.append(col)
            vals.append(f":{param or col}")

    add("student_id")
    add("date")
    add("present_minutes")
    add("absent_minutes")
    add("tardy_minutes")

    cols_sql = ", ".join(ins_cols)

    # Detect constraint for ON CONFLICT
    uqs = {u["name"]: u for u in insp.get_unique_constraints(ADS_TBL)}
    uq_name = None
    for name, meta in uqs.items():
        if set(meta.get("column_names") or []) == {"student_id", "date"}:
            uq_name = name
            break

    if bind.dialect.name == "postgresql" and uq_name:
        sql = sa.text(
            f"INSERT INTO {ADS_TBL} ({cols_sql}) VALUES ({', '.join(vals)}) "
            f"ON CONFLICT ON CONSTRAINT {uq_name} DO NOTHING"
        )
    else:
        # Portable guard: INSERT … SELECT … WHERE NOT EXISTS …
        select_list = ", ".join(vals)
        guard = (
            f" WHERE NOT EXISTS (SELECT 1 FROM {ADS_TBL} t "
            f"WHERE t.student_id = :student_id AND t.date = :date)"
        )
        sql = sa.text(
            f"INSERT INTO {ADS_TBL} ({cols_sql}) SELECT {select_list}{guard}"
        )

    return sql, cols


# ---- Migration ---------------------------------------------------------------
def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    _ensure_schema(bind)

    if not insp.has_table(ADS_TBL):
        log.info("[%s] Table %s missing; nothing to populate.", revision, ADS_TBL)
        return

    csv_path, csv_rows = _write_csv(bind)
    reader, fobj = _open_csv(csv_path)

    insert_stmt, cols = _insert_sql(bind)
    log.debug("[%s] Insert SQL: %s", revision, getattr(insert_stmt, "text", str(insert_stmt)))

    def _to_int(s: Optional[str], default: int = 0) -> int:
        try:
            return int(s) if s not in (None, "") else default
        except Exception:
            return default

    total = inserted = skipped = 0
    try:
        with _outer_tx(bind):
            for idx, raw in enumerate(reader, start=1):
                total += 1
                if not raw:
                    continue
                row = { (k.strip() if isinstance(k, str) else k): (v.strip() if isinstance(v, str) else v)
                        for k, v in raw.items() }

                sid = row.get("student_id") or None
                dt  = row.get("date") or None
                pm  = _to_int(row.get("present_minutes"), ADS_PRESENT_DEFAULT)
                am  = _to_int(row.get("absent_minutes"), ADS_ABSENT_DEFAULT)
                tm  = _to_int(row.get("tardy_minutes"), ADS_TARDY_DEFAULT)

                if not sid or not dt:
                    skipped += 1
                    if LOG_ROWS:
                        log.warning("[%s] row %d missing student_id/date — skipping: %r", revision, idx, row)
                    continue

                params = {
                    "student_id": sid,
                    "date": dt,  # string 'YYYY-MM-DD' is fine for psycopg2 DATE
                    "present_minutes": pm,
                    "absent_minutes": am,
                    "tardy_minutes": tm,
                }

                # Keep only real columns
                params = {k: v for k, v in params.items() if k in cols}

                try:
                    bind.execute(insert_stmt, params)
                    inserted += 1
                    if LOG_ROWS:
                        log.info("[%s] row %d INSERT ok (student=%s, date=%s, pm=%s, am=%s, tm=%s)",
                                 revision, idx, sid, dt, pm, am, tm)
                except Exception:
                    skipped += 1
                    if LOG_ROWS:
                        log.exception("[%s] row %d INSERT failed; params=%r", revision, idx, params)

    finally:
        try:
            fobj.close()
        except Exception:
            pass

    log.info("[%s] CSV rows=%d, inserted=%d, skipped=%d (file=%s)",
             revision, total, inserted, skipped, csv_path)

    if ABORT_IF_ZERO and csv_rows > 0 and inserted == 0:
        raise RuntimeError(f"[{revision}] No rows inserted; set ADS_LOG_ROWS=1 for per-row details.")


def downgrade() -> None:
    """
    Best-effort removal using the same CSV (if present): delete rows by (student_id, date).
    """
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if not insp.has_table(ADS_TBL):
        return

    csv_path = _default_output_path(CSV_NAME)
    if not csv_path.exists():
        log.info("[%s] downgrade: CSV %s not found; skipping delete.", revision, csv_path)
        return

    reader, fobj = _open_csv(csv_path)
    deleted = 0
    try:
        with _outer_tx(bind):
            for raw in reader:
                sid = (raw.get("student_id") or "").strip()
                dt  = (raw.get("date") or "").strip()
                if not sid or not dt:
                    continue
                try:
                    res = bind.execute(
                        sa.text(
                            f"DELETE FROM {ADS_TBL} WHERE student_id = :sid AND date = :dt"
                        ),
                        {"sid": sid, "dt": dt},
                    )
                    try:
                        deleted += res.rowcount or 0
                    except Exception:
                        pass
                except Exception:
                    if LOG_ROWS:
                        log.exception("[%s] downgrade delete failed for (%s,%s)", revision, sid, dt)
    finally:
        try:
            fobj.close()
        except Exception:
            pass

    log.info("[%s] downgrade removed ~%s rows from %s (based on CSV).",
             revision, deleted, ADS_TBL)