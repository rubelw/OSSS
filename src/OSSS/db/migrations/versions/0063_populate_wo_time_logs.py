"""Generate + populate work_order_time_logs from CSV (self-contained).

- First, generate work_order_time_logs.csv using live DB IDs (work_orders/users),
  mirroring the standalone tool's behavior but reusing Alembic's connection.
- Then, read the CSV and insert into work_order_time_logs.
- Robust path handling, ISO timestamp parsing, decimals, and verbose logging.

Env knobs:
  WOTL_OUT               : optional path to CSV file or its parent directory
  WOTL_ROWS              : how many rows to generate (default 200)
  WOTL_SEED              : random seed for reproducible generation
  WOTL_LOG_LEVEL         : DEBUG|INFO|... (default INFO)
  WOTL_LOG_ROWS          : 1 to log per-row inserts
  WOTL_ABORT_IF_ZERO     : 1 to raise if no rows inserted
  WOTL_SQL_ECHO          : 1 to echo SQL engine logs
"""

from __future__ import annotations

import os, csv, logging, random, re, json, time
from pathlib import Path
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from contextlib import nullcontext

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

# ---- Alembic identifiers ----
revision = "0063_populate_wo_time_logs"
down_revision = "0062_populate_users"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

# ---- Tables ----
WOTL_TBL     = "work_order_time_logs"
ORDERS_TBL   = "work_orders"
USERS_TBL    = "users"

CSV_NAME     = "work_order_time_logs.csv"

# ---- Logging knobs ----
LOG_LVL        = os.getenv("WOTL_LOG_LEVEL", "INFO").upper()
LOG_ROWS       = os.getenv("WOTL_LOG_ROWS", "0") == "1"
ABORT_IF_ZERO  = os.getenv("WOTL_ABORT_IF_ZERO", "0") == "1"
SQL_ECHO       = os.getenv("WOTL_SQL_ECHO", "0") == "1"

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
    if v is None:
        return None
    if isinstance(v, datetime):
        return v
    s = str(v).strip()
    try:
        # Accept basic ISO with optional trailing Z
        if s.endswith("Z"):
            s = s[:-1]
            # naive -> as UTC
            return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)
        return datetime.fromisoformat(s)
    except Exception:
        return None

def _parse_decimal(v):
    v = _none_if_blank(v)
    if v is None: return None
    try:
        return _dec2(v)
    except (InvalidOperation, ValueError, TypeError):
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

def _csv_default_path() -> Path:
    """Default CSV path in the same versions directory as this migration."""
    here = Path(__file__).resolve()
    return here.with_name(CSV_NAME)

def _resolve_out_path() -> Path:
    """Honor WOTL_OUT (file or directory). If directory, append CSV_NAME."""
    raw = os.getenv("WOTL_OUT", "").strip()
    if raw:
        p = Path(raw)
        if p.is_dir():
            return p / CSV_NAME
        return p
    return _csv_default_path()

def _find_csv(name: str, envvars: list[str] | None = None) -> Path | None:
    """Locate CSV with robust env-var handling and verbose diagnostics."""
    here = Path(__file__).resolve()
    candidates: list[Path] = []

    # allow multiple env var names; ignore blanks; expand dirs -> file inside
    for ev in (envvars or []):
        raw = os.getenv(ev)
        if not raw:
            continue
        p = Path(raw)
        candidates.append(p / name if p.is_dir() else p)

    # common locations
    candidates += [
        here.with_name(name),
        here.parent / "data" / name,
        here.parent.parent / "data" / name,
        Path.cwd() / name,
        Path("/mnt/data") / name,
    ]

    for p in candidates:
        try:
            if p.exists() and p.is_file():
                log.info("[%s] using CSV: %s", revision, p)
                return p
            else:
                log.debug("[%s] CSV candidate not usable: %s (exists=%s, is_file=%s)",
                          revision, p, p.exists() if p else None, p.is_file() if p else None)
        except Exception:
            log.debug("[%s] CSV candidate check failed: %r", revision, p, exc_info=True)

    log.error("[%s] CSV %s not found. Tried: %s", revision, name, ", ".join(map(str, candidates)))
    return None

def _open_csv(csv_path: Path):
    if not csv_path or not csv_path.exists() or not csv_path.is_file():
        raise FileNotFoundError(f"{revision}: CSV path is not a file: {csv_path!r}")
    f = csv_path.open("r", encoding="utf-8", newline="")
    reader = csv.DictReader(f)
    return reader, f

# ---- CSV GENERATION (inline tool) -------------------------------------------
def _fetch_ids(bind, table: str) -> list[str]:
    try:
        # Force public schema just in case
        bind.execute(sa.text("SET search_path TO public"))
    except Exception:
        pass
    rows = bind.execute(sa.text(f"SELECT id FROM public.{table}")).fetchall()
    return [str(r[0]) for r in rows]

def _generate_csv(bind) -> Path:
    """Generate CSV similar to the provided script, but using Alembic bind."""
    out = _resolve_out_path()
    out.parent.mkdir(parents=True, exist_ok=True)
    rows = int(os.getenv("WOTL_ROWS", "200"))
    seed = os.getenv("WOTL_SEED")

    rng = random.Random(seed)

    log.info("[%s] [wotl] generating CSV …", revision)
    wo_ids = _fetch_ids(bind, ORDERS_TBL)
    user_ids = _fetch_ids(bind, USERS_TBL)

    if not wo_ids:
        log.warning("[%s] [wotl] no work_orders found; nothing to generate", revision)
        return out
    if not user_ids:
        log.warning("[%s] [wotl] no users found; nothing to generate", revision)
        return out

    now = datetime.now(timezone.utc)
    fields = ["work_order_id","user_id","started_at","ended_at","hours","hourly_rate","cost","notes"]

    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(fields)
        for i in range(rows):
            wo  = rng.choice(wo_ids)
            uid = rng.choice(user_ids)
            # start sometime in the last 60 days
            start = now - timedelta(days=rng.randint(0,60), hours=rng.randint(0,18), minutes=rng.randint(0,59))
            dur_hours = rng.uniform(0.5, 8.0)
            end   = start + timedelta(hours=dur_hours)
            hours = _dec2(dur_hours)
            rate  = _dec2(rng.choice([20,22.5,25,27.5,30,35,40,45,50]))
            cost  = _dec2(hours * rate)
            notes = rng.choice(["", "Routine maintenance", "Emergency call", "Follow-up", "Preventive check"])
            w.writerow([wo, uid, start.isoformat(), end.isoformat(), f"{hours:.2f}", f"{rate:.2f}", f"{cost:.2f}", notes])

    log.info("[%s] [wotl] wrote %d rows -> %s", revision, rows, out)
    return out

# ---- Insert builder ----------------------------------------------------------
def _insert_sql(bind) -> sa.sql.elements.TextClause:
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns(WOTL_TBL)}

    ins_cols = ["id"]
    vals     = ["gen_random_uuid()"]

    def add(col):
        if col in cols:
            ins_cols.append(col)
            vals.append(f":{col}")

    for c in ["work_order_id","user_id","started_at","ended_at","hours","hourly_rate","cost","notes"]:
        add(c)

    if "created_at" in cols: ins_cols.append("created_at"); vals.append("now()")
    if "updated_at" in cols: ins_cols.append("updated_at"); vals.append("now()")

    sql = sa.text(f"INSERT INTO {WOTL_TBL} ({', '.join(ins_cols)}) VALUES ({', '.join(vals)}) RETURNING id")
    return sql

# ---- Migration ---------------------------------------------------------------
def upgrade() -> None:
    t0 = time.perf_counter()
    bind = op.get_bind()

    log.info("[%s] === BEGIN upgrade ===", revision)

    # 1) Generate the CSV first (using live DB ids)
    out_path = _generate_csv(bind)

    # 2) Find/validate CSV path (honor env var alias too)
    csv_path = None
    if out_path and out_path.exists():
        csv_path = out_path
        log.info("[%s] using freshly generated CSV: %s", revision, csv_path)
    else:
        csv_path = _find_csv(CSV_NAME, envvars=["WOTL_OUT"])
        if not csv_path:
            raise RuntimeError(f"[{revision}] {CSV_NAME} not found after generation")

    reader, fobj = _open_csv(csv_path)

    insert_stmt = _insert_sql(bind)

    inserted = skipped = 0
    try:
        with _outer_tx(bind):
            for idx, raw in enumerate(reader, start=1):
                row = { (k.strip() if isinstance(k,str) else k): (v.strip() if isinstance(v, str) else v)
                        for k, v in (raw or {}).items() }

                params = {
                    "work_order_id": _none_if_blank(row.get("work_order_id")),
                    "user_id":       _none_if_blank(row.get("user_id")),
                    "started_at":    _parse_dt(row.get("started_at")),
                    "ended_at":      _parse_dt(row.get("ended_at")),
                    "hours":         _parse_decimal(row.get("hours")),
                    "hourly_rate":   _parse_decimal(row.get("hourly_rate")),
                    "cost":          _parse_decimal(row.get("cost")),
                    "notes":         row.get("notes"),
                }

                if LOG_ROWS:
                    log.info("[%s] row %d params: %r", revision, idx, params)

                # rudimentary validation
                if not params["work_order_id"] or not params["user_id"]:
                    skipped += 1
                    log.warning("[%s] row %d missing work_order_id or user_id; skipping", revision, idx)
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

    log.info("[%s] CSV inserted: %d rows; skipped: %d", revision, inserted, skipped)
    dt = time.perf_counter() - t0
    if ABORT_IF_ZERO and inserted == 0:
        raise RuntimeError(f"[{revision}] No rows inserted from CSV; see logs.")
    log.info("[%s] === END upgrade (%.3fs) ===", revision, dt)

def downgrade() -> None:
    # Best-effort: nothing to do — leave time logs in place.
    log.info("[%s] downgrade: no-op (data migration).", revision)


# ---- Standalone execution support (env-driven DB URL) -----------------------
# Allows running this migration file directly (outside Alembic) using env vars:
#   OSSS_DB_URL="postgresql+asyncpg://osss:password@localhost:5433/osss"
# or compose from parts:
#   OSSS_DB_HOST="127.0.0.1"
#   OSSS_DB_PORT="5433"
#   OSSS_DB_NAME="osss"
#   OSSS_DB_USER="osss"
#   OSSS_DB_PASSWORD="password"
def _env_db_url() -> str:
    url = os.getenv("OSSS_DB_URL")
    if url:
        return url
    host = os.getenv("OSSS_DB_HOST", "127.0.0.1")
    port = os.getenv("OSSS_DB_PORT", "5433")
    name = os.getenv("OSSS_DB_NAME", "osss")
    user = os.getenv("OSSS_DB_USER", "osss")
    pwd  = os.getenv("OSSS_DB_PASSWORD", "password")
    return f"postgresql://{user}:{pwd}@{host}:{port}/{name}"

def _to_sync_dsn(url: str) -> str:
    # migration body is synchronous; normalize asyncpg DSN to sync
    if url.startswith("postgresql+asyncpg://"):
        return "postgresql://" + url.split("postgresql+asyncpg://", 1)[1]
    return url

if __name__ == "__main__":
    # Run the migration logic directly, outside Alembic, using env-provided DB URL
    try:
        dsn = _to_sync_dsn(_env_db_url())
        engine = sa.create_engine(dsn, echo=SQL_ECHO, future=True)
        with engine.begin() as conn:
            # Monkey-patch Alembic's op.get_bind() to return our connection
            op.get_bind = lambda: conn  # type: ignore[assignment]
            upgrade()
    except Exception as _e:
        import traceback
        print(f"[{revision}] standalone execution failed: {_e}\\n{traceback.format_exc()}")
        raise
