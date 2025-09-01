"""Populate motions from CSV (auto-generate CSV each run, robust parsing, no manual transactions)."""

from __future__ import annotations

import os, csv, logging, random, re
from pathlib import Path
from contextlib import nullcontext
from datetime import datetime
from itertools import cycle
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from sqlalchemy.dialects import postgresql as pg

from alembic import op
import sqlalchemy as sa

# ---- Alembic identifiers ----
revision = "0069_populate_webhooks"
# If your head before this migration is different, adjust the down_revision accordingly.
down_revision = "0068_populate_motions"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")



# ---- Config / env toggles ----------------------------------------------------
LOG_LVL       = os.getenv("WBK_LOG_LEVEL", "INFO").upper()
LOG_SQL       = os.getenv("WBK_LOG_SQL", "0") == "1"
LOG_ROWS      = os.getenv("WBK_LOG_ROWS", "0") == "1"
ABORT_IF_ZERO = os.getenv("WBK_ABORT_IF_ZERO", "0") == "1"

CSV_ENV   = "WEBHOOKS_CSV_PATH"
CSV_NAME  = "webhooks.csv"

# Generation knobs
SEED_ROWS       = int(os.getenv("WEBHOOKS_ROWS", "12"))
SEED_BASE_URL   = os.getenv("WEBHOOKS_BASE_URL", "https://seed.osss.local/webhooks")
SEED_EVENTS     = os.getenv(
    "WEBHOOKS_EVENTS",
    ",".join([
        "work_order.created",
        "work_order.updated",
        "work_order.closed",
        "work_order_time_log.created",
        "work_order_part.added",
        "maintenance_request.created",
        "maintenance_request.converted",
    ]),
).split(",")

logging.getLogger("alembic.runtime.migration").setLevel(getattr(logging, LOG_LVL, logging.INFO))
logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO if LOG_SQL else getattr(logging, LOG_LVL, logging.INFO))

# ---- Tables ------------------------------------------------------------------
WEBHOOKS_TBL = "webhooks"

# ---- Helpers -----------------------------------------------------------------
_norm_ws_re = re.compile(r"\s+")

def _candidate_paths(name: str) -> list[Path]:
    """Search common places; co-locate with this migration by default."""
    here = Path(__file__).resolve()
    envp = os.getenv(CSV_ENV)
    paths: list[Path] = []
    if envp:
        p = Path(envp)
        paths.append(p / name if p.is_dir() else p)
    paths += [
        here.with_name(name),
        here.parent / name,
        here.parent / "data" / name,
        here.parent.parent / "data" / name,
        Path.cwd() / name,
        Path("/mnt/data") / name,
    ]
    # de-dup while preserving order
    seen, uniq = set(), []
    for p in paths:
        try:
            key = str(p.resolve())
        except Exception:
            key = str(p)
        if key not in seen:
            uniq.append(p); seen.add(key)
    return uniq

def _locate_existing_csv(name: str) -> Path | None:
    for p in _candidate_paths(name):
        if p.exists() and p.is_file():
            log.info("[%s] using CSV: %s", revision, p)
            return p
    return None

def _default_output_path(name: str) -> Path:
    envp = os.getenv(CSV_ENV)
    if envp:
        p = Path(envp)
        return (p / name) if p.is_dir() else p
    return Path(__file__).resolve().with_name(name)

def _generate_csv() -> Path:
    """Create a CSV with deterministic-ish seed data."""
    out = _default_output_path(CSV_NAME)
    out.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    # build some varied event sets
    event_sets = [
        ["work_order.created", "work_order.updated"],
        ["work_order.closed"],
        ["work_order_time_log.created"],
        ["work_order_part.added"],
        ["maintenance_request.created"],
        ["maintenance_request.created", "maintenance_request.converted"],
        SEED_EVENTS[:3],
        SEED_EVENTS[-3:],
    ]
    # produce SEED_ROWS rows, cycling event_sets
    for i in range(SEED_ROWS):
        url = f"{SEED_BASE_URL}/endpoint-{i+1}"
        secret = "auto-" + secrets.token_hex(12)
        events = event_sets[i % len(event_sets)]
        rows.append({"target_url": url, "secret": secret, "events": json.dumps(events)})

    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["target_url","secret","events"])
        w.writeheader()
        w.writerows(rows)

    log.info("[%s] generated %d webhook rows -> %s", revision, len(rows), out)
    return out

def _ensure_csv() -> Path:
    p = _locate_existing_csv(CSV_NAME)
    if p:
        return p
    log.warning("[%s] %s not found — auto-generating …", revision, CSV_NAME)
    return _generate_csv()

def _open_csv(csv_path: Path):
    f = csv_path.open("r", encoding="utf-8", newline="")
    reader = csv.DictReader(f)
    log.info("[%s] CSV headers: %s", revision, reader.fieldnames)
    return reader, f

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

def _parse_events(val) -> list[str] | None:
    """Accept JSON array, or comma/semicolon-separated string; normalize to list[str]."""
    if val is None:
        return None
    if isinstance(val, list):
        return [str(x).strip() for x in val if str(x).strip()]
    s = str(val).strip()
    if not s:
        return None
    # try JSON first
    if s.startswith("["):
        try:
            arr = json.loads(s)
            if isinstance(arr, list):
                return [str(x).strip() for x in arr if str(x).strip()]
        except Exception:
            pass
    # fallback: split by comma/semicolon/space
    parts = re.split(r"[;,]", s)
    norm = [p.strip() for p in parts if p and p.strip()]
    return norm or None

def _insert_sql(bind):
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns(WEBHOOKS_TBL)}
    ins_cols = ["id"]
    vals     = ["gen_random_uuid()"]
    params   = {}

    def add(col, param):
        if col in cols:
            ins_cols.append(col)
            vals.append(f":{param}")
            params[param] = None

    add("target_url","target_url")
    add("secret","secret")
    add("events","events")
    if "created_at" in cols: ins_cols.append("created_at"); vals.append("now()")
    if "updated_at" in cols: ins_cols.append("updated_at"); vals.append("now()")

    sql = sa.text(f"INSERT INTO {WEBHOOKS_TBL} ({', '.join(ins_cols)}) VALUES ({', '.join(vals)})")
    if "events" in params:
        sql = sql.bindparams(sa.bindparam("events", type_=pg.JSONB))
    return sql

# ---- Migration ---------------------------------------------------------------
def upgrade() -> None:
    bind = op.get_bind()
    csv_path = _ensure_csv()
    reader, fobj = _open_csv(csv_path)

    insert_stmt = _insert_sql(bind)

    total = inserted = skipped = 0
    try:
        with _outer_tx(bind):
            for idx, raw in enumerate(reader, start=1):
                total += 1
                row = { (k.strip() if isinstance(k,str) else k): (v.strip() if isinstance(v,str) else v)
                        for k, v in (raw or {}).items() }
                target_url = row.get("target_url")
                if not target_url:
                    skipped += 1
                    if LOG_ROWS:
                        log.warning("[%s] row %d missing target_url — skipping", revision, idx)
                    continue

                secret = row.get("secret") or None
                events = _parse_events(row.get("events"))

                params = {"target_url": target_url, "secret": secret, "events": events}
                if LOG_ROWS:
                    log.info("[%s] row %d -> %r", revision, idx, params)

                try:
                    with _per_row_tx(bind):
                        bind.execute(insert_stmt, params)
                        inserted += 1
                except Exception:
                    skipped += 1
                    log.exception("[%s] row %d failed to insert; params=%r", revision, idx, params)
    finally:
        try: fobj.close()
        except Exception: pass

    log.info("[%s] CSV rows=%d, inserted=%d, skipped=%d", revision, total, inserted, skipped)
    if ABORT_IF_ZERO and inserted == 0:
        raise RuntimeError(f"[{revision}] No rows inserted; enable WBK_LOG_ROWS=1 for per-row details.")

def downgrade() -> None:
    # Best-effort clean-up of the auto-generated entries by recognizable base URL.
    bind = op.get_bind()
    try:
        res = bind.execute(
            sa.text(f"DELETE FROM {WEBHOOKS_TBL} WHERE target_url LIKE :p"),
            {"p": f"{SEED_BASE_URL}/%"},
        )
        try:
            log.info("[%s] downgrade deleted rows: %s", revision, res.rowcount)
        except Exception:
            pass
    except Exception:
        log.info("[%s] downgrade: best-effort delete failed; leaving data intact.", revision)