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
revision = "0088_populate_section_mtg"
down_revision = "0087_populate_att_day_sum"  # update if needed
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")


# ---- Config / env toggles ----------------------------------------------------
LOG_LVL        = os.getenv("SM_LOG_LEVEL", "INFO").upper()
LOG_SQL        = os.getenv("SM_LOG_SQL", "1") == "1"
LOG_ROWS       = os.getenv("SM_LOG_ROWS", "1") == "1"
ABORT_IF_ZERO  = os.getenv("SM_ABORT_IF_ZERO", "1") == "1"

CSV_ENV        = "SECTION_MEETINGS_CSV_PATH"
CSV_NAME       = "section_meetings.csv"

# how many meetings to create per section (spread across weekdays)
SM_PER_SECTION   = int(os.getenv("SM_PER_SECTION", "2"))
# cycle days among this set; default Mon..Fri using 1..5. Use "0-6" if your app uses Sun..Sat.
SM_DAYS_START    = int(os.getenv("SM_DAYS_START", "1"))
SM_DAYS_END      = int(os.getenv("SM_DAYS_END", "5"))
# Assign a period/room if available?
SM_ASSIGN_PERIOD = os.getenv("SM_ASSIGN_PERIOD", "1") == "1"
SM_ASSIGN_ROOM   = os.getenv("SM_ASSIGN_ROOM", "0") == "1"
SM_SEED          = os.getenv("SM_SEED")  # for deterministic choices

# ---- Table names -------------------------------------------------------------
SECTIONS_TBL = "course_sections"
PERIODS_TBL  = "periods"
ROOMS_TBL    = "rooms"
SM_TBL       = "section_meetings"

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
    """Ensure uq_section_meeting(section_id, day_of_week, period_id) exists."""
    insp = sa.inspect(bind)
    if not insp.has_table(SM_TBL):
        return
    uqs = {u["name"]: u for u in insp.get_unique_constraints(SM_TBL)}
    want_cols = ["section_id", "day_of_week", "period_id"]
    if "uq_section_meeting" in uqs:
        if uqs["uq_section_meeting"]["column_names"] != want_cols:
            op.drop_constraint("uq_section_meeting", SM_TBL, type_="unique")
            try:
                op.create_unique_constraint("uq_section_meeting", SM_TBL, want_cols)
            except Exception:
                pass
    else:
        try:
            op.create_unique_constraint("uq_section_meeting", SM_TBL, want_cols)
        except Exception:
            pass


def _write_csv(bind) -> tuple[Path, int]:
    """
    (Re)generate section_meetings.csv from current course_sections (+ optional periods/rooms).
    Returns (path, number_of_rows_written).
    """
    out = _default_output_path(CSV_NAME)
    out.parent.mkdir(parents=True, exist_ok=True)

    insp = sa.inspect(bind)
    have_sections = insp.has_table(SECTIONS_TBL)
    have_periods  = insp.has_table(PERIODS_TBL)
    have_rooms    = insp.has_table(ROOMS_TBL)

    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        # created_at/updated_at are omitted; DB defaults will populate them.
        w.writerow(["section_id", "day_of_week", "period_id", "room_id"])

        if not have_sections:
            log.warning("[%s] Missing %s; wrote header-only CSV: %s", revision, SECTIONS_TBL, out)
            return out, 0

        sections = [str(r[0]) for r in bind.execute(sa.text(f"SELECT id FROM {SECTIONS_TBL} ORDER BY id")).fetchall()]
        periods  = [str(r[0]) for r in bind.execute(sa.text(f"SELECT id FROM {PERIODS_TBL} ORDER BY id")).fetchall()] if (have_periods and SM_ASSIGN_PERIOD) else []
        rooms    = [str(r[0]) for r in bind.execute(sa.text(f"SELECT id FROM {ROOMS_TBL} ORDER BY id")).fetchall()] if (have_rooms and SM_ASSIGN_ROOM) else []

        if not sections or SM_PER_SECTION <= 0:
            log.info("[%s] Nothing to seed (sections=%d, per_section=%d); header-only CSV: %s",
                     revision, len(sections), SM_PER_SECTION, out)
            return out, 0

        rng = random.Random(SM_SEED)
        days = list(range(SM_DAYS_START, SM_DAYS_END + 1))  # inclusive

        rows = 0
        for idx, sid in enumerate(sections):
            for n in range(SM_PER_SECTION):
                day = days[(idx + n) % len(days)] if days else 1
                pid = rng.choice(periods) if periods else ""
                rid = rng.choice(rooms) if rooms else ""
                w.writerow([sid, day, pid, rid])
                rows += 1

    log.info("[%s] CSV generated with %d rows => %s (sections=%d, per_section=%d, days=%s, periods=%d, rooms=%d)",
             revision, rows, out, len(sections), SM_PER_SECTION, f"{SM_DAYS_START}-{SM_DAYS_END}", len(periods), len(rooms))
    return out, rows


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
    Build INSERT for section_meetings. We use a portable NOT-EXISTS guard that
    handles NULL period_id via `IS NOT DISTINCT FROM` so reruns remain idempotent.
    """
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns(SM_TBL)}

    ins_cols, vals = [], []

    def add(col: str, param: Optional[str] = None):
        if col in cols:
            ins_cols.append(col)
            vals.append(f":{param or col}")

    add("section_id")
    add("day_of_week")
    add("period_id")
    add("room_id")

    cols_sql = ", ".join(ins_cols)
    select_list = ", ".join(vals)

    # NOT EXISTS guard with NULL-safe comparison for period_id
    guard = (
        f" WHERE NOT EXISTS (SELECT 1 FROM {SM_TBL} t "
        f"WHERE t.section_id = :section_id "
        f"AND t.day_of_week = :day_of_week "
        f"AND t.period_id IS NOT DISTINCT FROM :period_id)"
    )

    sql = sa.text(f"INSERT INTO {SM_TBL} ({cols_sql}) SELECT {select_list}{guard}")
    return sql, cols


# ---- Migration ---------------------------------------------------------------
def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    _ensure_schema(bind)

    if not insp.has_table(SM_TBL):
        log.info("[%s] Table %s missing; nothing to populate.", revision, SM_TBL)
        return

    csv_path, csv_rows = _write_csv(bind)
    reader, fobj = _open_csv(csv_path)

    insert_stmt, cols = _insert_sql(bind)
    log.debug("[%s] Insert SQL: %s", revision, getattr(insert_stmt, "text", str(insert_stmt)))

    def _to_int(s: Optional[str], default: int = 1) -> int:
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

                sid = row.get("section_id") or None
                dow = _to_int(row.get("day_of_week"), 1)
                pid = row.get("period_id") or None
                rid = row.get("room_id") or None
                if pid in ("", "null", "NULL"): pid = None
                if rid in ("", "null", "NULL"): rid = None

                if not sid:
                    skipped += 1
                    if LOG_ROWS:
                        log.warning("[%s] row %d missing section_id — skipping: %r", revision, idx, row)
                    continue

                params = {
                    "section_id": sid,
                    "day_of_week": dow,
                    "period_id": pid,
                    "room_id": rid,
                }
                params = {k: v for k, v in params.items() if k in cols}

                try:
                    bind.execute(insert_stmt, params)
                    inserted += 1
                    if LOG_ROWS:
                        log.info("[%s] row %d INSERT ok (section=%s, day=%s, period=%s, room=%s)",
                                 revision, idx, sid, dow, pid, rid)
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
        raise RuntimeError(f"[{revision}] No rows inserted; set SM_LOG_ROWS=1 for per-row details.")


def downgrade() -> None:
    """
    Best-effort removal using the same CSV (if present): delete rows by (section_id, day_of_week, period_id).
    """
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if not insp.has_table(SM_TBL):
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
                sid = (raw.get("section_id") or "").strip()
                dow = (raw.get("day_of_week") or "").strip()
                pid = (raw.get("period_id") or "").strip()
                if not sid or not dow:
                    continue
                params = {"sid": sid, "dow": int(dow), "pid": (None if pid in ("", "null", "NULL") else pid)}
                try:
                    res = bind.execute(
                        sa.text(
                            f"DELETE FROM {SM_TBL} "
                            f"WHERE section_id = :sid AND day_of_week = :dow AND period_id IS NOT DISTINCT FROM :pid"
                        ),
                        params,
                    )
                    try:
                        deleted += res.rowcount or 0
                    except Exception:
                        pass
                except Exception:
                    if LOG_ROWS:
                        log.exception("[%s] downgrade delete failed for (%s,%s,%s)", revision, sid, dow, pid)
    finally:
        try:
            fobj.close()
        except Exception:
            pass

    log.info("[%s] downgrade removed ~%s rows from %s (based on CSV).",
             revision, deleted, SM_TBL)