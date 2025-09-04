# src/OSSS/db/migrations/versions/0081_populate_audit_logs.py
from __future__ import annotations

import os, csv, json, logging, uuid, random
from pathlib import Path
from contextlib import nullcontext
from typing import Optional

from alembic import op
import sqlalchemy as sa

# ---- Alembic identifiers ----
revision = "0086_populate_attendance"
down_revision = "0085_populate_approvals"  # update if needed
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")


# ---- Config / env toggles ----------------------------------------------------
LOG_LVL        = os.getenv("ATT_LOG_LEVEL", "INFO").upper()
LOG_SQL        = os.getenv("ATT_LOG_SQL", "1") == "1"
LOG_ROWS       = os.getenv("ATT_LOG_ROWS", "1") == "1"
ABORT_IF_ZERO  = os.getenv("ATT_ABORT_IF_ZERO", "1") == "1"  # kept for compatibility; no longer raises

CSV_ENV        = "ATTENDANCE_CSV_PATH"
CSV_NAME       = "attendance.csv"

ATT_PER_MEETING = int(os.getenv("ATT_PER_MEETING", "3"))   # attendees per meeting
ATT_STATUS      = os.getenv("ATT_STATUS", "present")       # default status for rows
ATT_SEED        = os.getenv("ATT_SEED")                    # fix RNG if provided

# ---- Table names -------------------------------------------------------------
ATTENDANCE_TBL = "attendance"
MEETINGS_TBL   = "meetings"
USERS_TBL      = "users"

# ---- Logging setup -----------------------------------------------------------
logging.getLogger("alembic.runtime.migration").setLevel(getattr(logging, LOG_LVL, logging.INFO))
_engine_logger = logging.getLogger("sqlalchemy.engine")
_engine_logger.setLevel(logging.INFO if LOG_SQL else getattr(logging, LOG_LVL, logging.INFO))


# ---- Helpers ----------------------------------------------------------------
def _outer_tx(conn):
    """Open a transaction only if one isn't already active (works in env.py patterns)."""
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


def _uuid_sql(bind) -> str:
    """Prefer gen_random_uuid(), fall back to uuid_generate_v4(), else parameterize."""
    if bind.dialect.name != "postgresql":
        return ":_uuid"
    try:
        bind.execute(sa.text("SELECT gen_random_uuid()"))
        return "gen_random_uuid()"
    except Exception:
        pass
    try:
        bind.execute(sa.text("SELECT uuid_generate_v4()"))
        return "uuid_generate_v4()"
    except Exception:
        pass
    return ":_uuid"


def _ensure_schema(bind):
    """Ensure the unique constraint (meeting_id, user_id) exists for ON CONFLICT."""
    insp = sa.inspect(bind)
    if not insp.has_table(ATTENDANCE_TBL):
        return
    uqs = {u["name"]: u for u in insp.get_unique_constraints(ATTENDANCE_TBL)}
    expected_cols = ["meeting_id", "user_id"]
    if "uq_attendance_meeting_user" in uqs:
        if uqs["uq_attendance_meeting_user"]["column_names"] != expected_cols:
            op.drop_constraint("uq_attendance_meeting_user", ATTENDANCE_TBL, type_="unique")
            try:
                op.create_unique_constraint("uq_attendance_meeting_user", ATTENDANCE_TBL, expected_cols)
            except Exception:
                pass
    else:
        try:
            op.create_unique_constraint("uq_attendance_meeting_user", ATTENDANCE_TBL, expected_cols)
        except Exception:
            pass


def _write_csv(bind) -> tuple[Path, int]:
    """
    (Re)generate attendance.csv from current meetings and users.
    Returns (path, number_of_rows_written).
    """
    out = _default_output_path(CSV_NAME)
    out.parent.mkdir(parents=True, exist_ok=True)

    insp = sa.inspect(bind)
    have_meetings = insp.has_table(MEETINGS_TBL)
    have_users    = insp.has_table(USERS_TBL)

    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        # We omit 'id' (server default generates), and omit arrived_at/left_at by default (NULL).
        w.writerow(["meeting_id", "user_id", "status", "arrived_at", "left_at"])

        if not (have_meetings and have_users):
            log.warning("[%s] Missing %s or %s; wrote header-only CSV: %s",
                        revision, MEETINGS_TBL, USERS_TBL, out)
            return out, 0

        meeting_ids = [str(r[0]) for r in bind.execute(sa.text(f"SELECT id FROM {MEETINGS_TBL} ORDER BY id")).fetchall()]
        user_ids    = [str(r[0]) for r in bind.execute(sa.text(f"SELECT id FROM {USERS_TBL} ORDER BY id")).fetchall()]

        log.info("[%s] Found meetings=%d, users=%d", revision, len(meeting_ids), len(user_ids))

        if not meeting_ids or not user_ids or ATT_PER_MEETING <= 0:
            log.info("[%s] Nothing to seed (meetings=%d, users=%d, per_meeting=%d); header-only CSV written: %s",
                     revision, len(meeting_ids), len(user_ids), ATT_PER_MEETING, out)
            return out, 0

        rng = random.Random(ATT_SEED)
        rows = 0
        for mid in meeting_ids:
            if len(user_ids) >= ATT_PER_MEETING:
                chosen = rng.sample(user_ids, ATT_PER_MEETING)
            else:
                # round-robin if fewer users than requested
                chosen = [user_ids[i % len(user_ids)] for i in range(ATT_PER_MEETING)]

            for uid in chosen:
                status = ATT_STATUS  # e.g., 'present' (default). Can be overridden via env.
                arrived_at = ""      # empty -> NULL
                left_at    = ""      # empty -> NULL
                w.writerow([mid, uid, status, arrived_at, left_at])
                rows += 1

    log.info("[%s] CSV generated with %d rows => %s", revision, rows, out)
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
    Build INSERT for attendance. If a unique (meeting_id, user_id) exists,
    use ON CONFLICT DO NOTHING; otherwise use SELECT … WHERE NOT EXISTS guard.
    """
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns(ATTENDANCE_TBL)}

    ins_cols, vals = [], []

    # We can omit 'id' entirely so server_default generates it.
    # If you prefer to populate id yourself, uncomment the next block.
    # uuid_expr = _uuid_sql(bind)
    # if "id" in cols:
    #     ins_cols.append("id")
    #     vals.append("gen_random_uuid()" if uuid_expr not in (":_uuid",) else uuid_expr)

    def add(col: str, param: Optional[str] = None):
        if col in cols:
            ins_cols.append(col)
            vals.append(f":{param or col}")

    add("meeting_id")
    add("user_id")
    add("status")
    add("arrived_at")
    add("left_at")

    cols_sql = ", ".join(ins_cols)

    # Detect constraint for ON CONFLICT
    uqs = {u["name"]: u for u in insp.get_unique_constraints(ATTENDANCE_TBL)}
    uq_name = None
    for name, meta in uqs.items():
        if set(meta.get("column_names") or []) == {"meeting_id", "user_id"}:
            uq_name = name
            break

    if bind.dialect.name == "postgresql" and uq_name:
        sql = sa.text(
            f"INSERT INTO {ATTENDANCE_TBL} ({cols_sql}) VALUES ({', '.join(vals)}) "
            f"ON CONFLICT ON CONSTRAINT {uq_name} DO NOTHING"
        )
        needs_uuid_param = False
    else:
        # Portable guard: INSERT … SELECT … WHERE NOT EXISTS …
        select_list = ", ".join(vals)
        guard = (
            f" WHERE NOT EXISTS (SELECT 1 FROM {ATTENDANCE_TBL} t "
            f"WHERE t.meeting_id = :meeting_id AND t.user_id = :user_id)"
        )
        sql = sa.text(
            f"INSERT INTO {ATTENDANCE_TBL} ({cols_sql}) SELECT {select_list}{guard}"
        )
        needs_uuid_param = False

    return sql, cols, needs_uuid_param


# ---- Migration ---------------------------------------------------------------
def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    _ensure_schema(bind)

    if not insp.has_table(ATTENDANCE_TBL):
        log.info("[%s] Table %s missing; nothing to populate.", revision, ATTENDANCE_TBL)
        return

    csv_path, csv_rows = _write_csv(bind)

    # Option A: if there are no data rows, skip instead of raising
    if csv_rows == 0:
        log.warning("[%s] no eligible rows; skipping (no %s/%s yet). CSV=%s",
                    revision, MEETINGS_TBL, USERS_TBL, csv_path)
        return

    reader, fobj = _open_csv(csv_path)

    insert_stmt, cols, needs_uuid_param = _insert_sql(bind)
    log.debug("[%s] Insert SQL: %s", revision, getattr(insert_stmt, "text", str(insert_stmt)))

    total = inserted = skipped = 0
    try:
        with _outer_tx(bind):
            for idx, raw in enumerate(reader, start=1):
                total += 1
                if not raw:
                    continue
                row = { (k.strip() if isinstance(k, str) else k): (v.strip() if isinstance(v, str) else v)
                        for k, v in raw.items() }

                meeting_id = row.get("meeting_id") or None
                user_id    = row.get("user_id") or None
                status     = row.get("status") or ATT_STATUS or None
                arrived_at = row.get("arrived_at") or None
                left_at    = row.get("left_at") or None

                # Normalize empty timestamps to NULL
                if arrived_at in ("", "null", "NULL"):
                    arrived_at = None
                if left_at in ("", "null", "NULL"):
                    left_at = None

                if not meeting_id or not user_id:
                    skipped += 1
                    if LOG_ROWS:
                        log.warning("[%s] row %d missing meeting_id/user_id — skipping: %r",
                                    revision, idx, row)
                    continue

                params = {
                    "meeting_id": meeting_id,
                    "user_id": user_id,
                    "status": status,
                    "arrived_at": arrived_at,
                    "left_at": left_at,
                }
                # Keep only params that exist as real columns (+ optional _uuid)
                params = {k: v for k, v in params.items() if (k in cols or k == "_uuid")}

                try:
                    bind.execute(insert_stmt, params)
                    inserted += 1
                    if LOG_ROWS:
                        log.info("[%s] row %d INSERT ok (meeting=%s, user=%s)",
                                 revision, idx, meeting_id, user_id)
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

    # Option A: no hard failure; just warn and exit if nothing inserted
    if csv_rows == 0 or inserted == 0:
        log.warning("[%s] no rows inserted (csv_rows=%d, inserted=%d); skipping", revision, csv_rows, inserted)
        return


def downgrade() -> None:
    """
    Best-effort removal using the same CSV (if present): delete rows by (meeting_id, user_id).
    """
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if not insp.has_table(ATTENDANCE_TBL):
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
                mid = (raw.get("meeting_id") or "").strip()
                uid = (raw.get("user_id") or "").strip()
                if not mid or not uid:
                    continue
                try:
                    res = bind.execute(
                        sa.text(
                            f"DELETE FROM {ATTENDANCE_TBL} "
                            f"WHERE meeting_id = :mid AND user_id = :uid"
                        ),
                        {"mid": mid, "uid": uid},
                    )
                    try:
                        deleted += res.rowcount or 0
                    except Exception:
                        pass
                except Exception:
                    if LOG_ROWS:
                        log.exception("[%s] downgrade delete failed for (%s,%s)", revision, mid, uid)
    finally:
        try:
            fobj.close()
        except Exception:
            pass

    log.info("[%s] downgrade removed ~%s rows from %s (based on CSV).",
             revision, deleted, ATTENDANCE_TBL)
