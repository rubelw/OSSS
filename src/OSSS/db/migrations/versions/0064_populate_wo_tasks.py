

from __future__ import annotations

import os, csv, logging, random, re, json, time
from pathlib import Path
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from contextlib import nullcontext

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg
from sqlalchemy import create_engine, text as sqltext


# ---- Alembic identifiers ----
revision = "0064_populate_wo_tasks"
down_revision = "0063_populate_wo_time_logs"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")


# ---- Tables / filenames ----
TASKS_TBL   = "work_order_tasks"
ORDERS_TBL  = "work_orders"
CSV_NAME    = "work_order_tasks.csv"

# ---- Logging knobs ----
LOG_LVL        = os.getenv("WOTASKS_LOG_LEVEL", "INFO").upper()
LOG_ROWS       = os.getenv("WOTASKS_LOG_ROWS", "0") == "1"
ABORT_IF_ZERO  = os.getenv("WOTASKS_ABORT_IF_ZERO", "0") == "1"
SQL_ECHO       = os.getenv("WOTASKS_SQL_ECHO", "0") == "1"

logging.getLogger("alembic.runtime.migration").setLevel(getattr(logging, LOG_LVL, logging.INFO))
logging.getLogger("alembic").setLevel(getattr(logging, LOG_LVL, logging.INFO))
logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO if SQL_ECHO else getattr(logging, LOG_LVL, logging.WARNING))

# ---- Helpers ----------------------------------------------------------------
_norm_ws_re = re.compile(r"\s+")

def _dec2(val: float | Decimal) -> Decimal:
    return Decimal(str(val)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

def _none_if_blank(v):
    if v is None: return None
    if isinstance(v, str) and v.strip() == "": return None
    return v

def _parse_dt(v):
    v = _none_if_blank(v)
    if v is None: return None
    if isinstance(v, datetime): return v
    s = str(v).strip()
    try:
        if s.endswith("Z"):
            s = s[:-1]
            return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)
        return datetime.fromisoformat(s)
    except Exception:
        return None

def _outer_tx(conn):
    try:
        if hasattr(conn, "get_transaction") and conn.get_transaction() is not None:
            return nullcontext()
        if hasattr(conn, "in_transaction") and conn.in_transaction():
            return nullcontext()
    except Exception:
        return nullcontext()
    return conn.begin()

def _per_row_tx(conn):
    try:
        return conn.begin_nested()
    except Exception:
        return nullcontext()

def _versions_dir_csv() -> Path:
    here = Path(__file__).resolve()
    return here.with_name(CSV_NAME)

def _resolve_out_path() -> Path:
    raw = os.getenv("WOTASKS_OUT", "").strip()
    if raw:
        p = Path(raw)
        return p / CSV_NAME if p.is_dir() else p
    return _versions_dir_csv()

# ---- Build sync DB URL from env ---------------------------------------------
def _build_sync_url_from_env() -> str:
    url = os.getenv("OSSS_DB_URL")
    if url:
        # convert asyncpg URL to sync psycopg2 if needed
        return url.replace("+asyncpg", "+psycopg2")
    host = os.getenv("OSSS_DB_HOST", "127.0.0.1")
    port = os.getenv("OSSS_DB_PORT", "5433")
    name = os.getenv("OSSS_DB_NAME", "osss")
    user = os.getenv("OSSS_DB_USER", "osss")
    pwd  = os.getenv("OSSS_DB_PASSWORD", "password")
    return f"postgresql+psycopg2://{user}:{pwd}@{host}:{port}/{name}"

# ---- CSV generation ----------------------------------------------------------
def _fetch_work_order_ids_via_env() -> list[str]:
    url = _build_sync_url_from_env()
    log.info("[%s] Connecting for CSV generation -> %s", revision, url)
    engine = create_engine(url, future=True)
    with engine.connect() as conn:
        try:
            conn.execute(sqltext("SET search_path TO public"))
        except Exception:
            pass
        rows = conn.execute(sqltext(f"SELECT id FROM public.{ORDERS_TBL}")).fetchall()
        return [str(r[0]) for r in rows]

def _generate_csv() -> Path:
    """Create CSV of tasks based on existing work_orders (env-driven connection)."""
    out = _resolve_out_path()
    out.parent.mkdir(parents=True, exist_ok=True)

    seed = os.getenv("WOTASKS_SEED")
    rng = random.Random(seed)

    min_tasks = int(os.getenv("WOTASKS_MIN", "1"))
    max_tasks = int(os.getenv("WOTASKS_MAX", "4"))
    max_tasks = max(max_tasks, min_tasks)

    wo_ids = _fetch_work_order_ids_via_env()
    if not wo_ids:
        log.warning("[%s] No work_orders found; CSV will be empty -> %s", revision, out)
        with out.open("w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(["work_order_id","seq","title","is_mandatory","status","completed_at","notes"])
        return out

    statuses = ["pending", "in_progress", "done"]
    title_templates = [
        "Initial inspection",
        "Gather materials",
        "Perform task",
        "Quality check",
        "Cleanup",
        "Finalize documentation",
    ]

    now = datetime.now(timezone.utc)

    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["work_order_id","seq","title","is_mandatory","status","completed_at","notes"])
        for wo in wo_ids:
            n = rng.randint(min_tasks, max_tasks)
            # deterministic but varied sequence/titles
            for seq in range(1, n + 1):
                title = rng.choice(title_templates)
                mandatory = "1" if rng.random() < 0.6 else "0"
                status = rng.choice(statuses)
                if status == "done":
                    # set a completion time in the last 30 days
                    completed = now - timedelta(days=rng.randint(0, 30), hours=rng.randint(0, 18))
                    completed_iso = completed.isoformat()
                else:
                    completed_iso = ""
                notes = rng.choice(["", "N/A", "Requires follow-up", "All good", "See photos attached"])
                w.writerow([wo, seq, title, mandatory, status, completed_iso, notes])

    log.info("[%s] wrote CSV -> %s", revision, out)
    return out

def _open_csv(csv_path: Path):
    if not csv_path or not csv_path.exists() or not csv_path.is_file():
        raise FileNotFoundError(f"{revision}: CSV path is not a file: {csv_path!r}")
    f = csv_path.open("r", encoding="utf-8", newline="")
    reader = csv.DictReader(f)
    return reader, f

# ---- Insert builder ----------------------------------------------------------
def _insert_sql(bind) -> sa.sql.elements.TextClause:
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns(TASKS_TBL)}
    ins_cols = ["id"]
    vals = ["gen_random_uuid()"]

    def add(c):
        if c in cols:
            ins_cols.append(c)
            vals.append(f":{c}")

    for c in ["work_order_id","seq","title","is_mandatory","status","completed_at","notes"]:
        add(c)

    if "created_at" in cols: ins_cols.append("created_at"); vals.append("now()")
    if "updated_at" in cols: ins_cols.append("updated_at"); vals.append("now()")

    sql = sa.text(f"INSERT INTO {TASKS_TBL} ({', '.join(ins_cols)}) VALUES ({', '.join(vals)}) RETURNING id")
    return sql

# ---- Migration ---------------------------------------------------------------
def upgrade() -> None:
    t0 = time.perf_counter()
    bind = op.get_bind()
    log.info("[%s] === BEGIN upgrade ===", revision)

    # 1) Generate CSV first (using env-driven connection to the DB)
    csv_path = _generate_csv()

    # 2) Read and insert
    reader, fobj = _open_csv(csv_path)
    insert_stmt = _insert_sql(bind)

    inserted = skipped = 0
    try:
        with _outer_tx(bind):
            for idx, raw in enumerate(reader, start=1):
                row = { (k.strip() if isinstance(k,str) else k): (v.strip() if isinstance(v,str) else v)
                        for k, v in (raw or {}).items() }

                params = {
                    "work_order_id": _none_if_blank(row.get("work_order_id")),
                    "seq":           int(row["seq"]) if _none_if_blank(row.get("seq")) else 1,
                    "title":         row.get("title") or "Task",
                    # column is Text with '0'/'1' default, keep as text:
                    "is_mandatory":  (row.get("is_mandatory") or "0").strip() or "0",
                    "status":        _none_if_blank(row.get("status")),
                    "completed_at":  _parse_dt(row.get("completed_at")),
                    "notes":         row.get("notes"),
                }

                if LOG_ROWS:
                    log.info("[%s] row %d params: %r", revision, idx, params)

                if not params["work_order_id"]:
                    skipped += 1
                    log.warning("[%s] row %d missing work_order_id; skipping", revision, idx)
                    continue

                try:
                    with _per_row_tx(bind):
                        bind.execute(insert_stmt, params)
                        inserted += 1
                except Exception:
                    skipped += 1
                    log.exception("[%s] row %d insert failed; params=%r", revision, idx, params)

    finally:
        try: fobj.close()
        except Exception: pass

    dt = time.perf_counter() - t0
    log.info("[%s] CSV inserted: %d rows; skipped: %d (%.3fs)", revision, inserted, skipped, dt)
    if ABORT_IF_ZERO and inserted == 0:
        raise RuntimeError(f"[{revision}] No rows inserted; see logs.")

def downgrade() -> None:
    # Data-only; leave tasks in place.
    log.info("[%s] downgrade: no-op.", revision)