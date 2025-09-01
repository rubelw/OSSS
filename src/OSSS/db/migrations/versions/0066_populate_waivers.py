"""Populate work_order_parts from CSV (flex headers + robust parsing + FK preflight + loud logging)."""

from __future__ import annotations
import os, csv, logging, re, secrets, json, random
from datetime import datetime, date, timedelta

from pathlib import Path
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from contextlib import nullcontext
from itertools import cycle
from sqlalchemy.dialects import postgresql as pg

from alembic import op
import sqlalchemy as sa

# ---- Alembic identifiers ----
revision = "0066_populate_waivers"
down_revision = "0065_populate_wo_parts"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")


# ---- Config / toggles --------------------------------------------------------
LOG_LVL       = os.getenv("WVR_LOG_LEVEL", "INFO").upper()
LOG_SQL       = os.getenv("WVR_LOG_SQL", "0") == "1"
LOG_ROWS      = os.getenv("WVR_LOG_ROWS", "0") == "1"
ABORT_IF_ZERO = os.getenv("WVR_ABORT_IF_ZERO", "0") == "1"

SCHEMA        = (os.getenv("WVR_SCHEMA", "public") or "").strip()
INSPECT_SCHEMA = None if SCHEMA == "" else SCHEMA

CSV_NAME      = "waiver.csv"   # per request
CSV_ENV       = "WAIVER_CSV_PATH"  # optional override dir/file via env
MAX_ROWS      = int(os.getenv("WVR_ROWS", "20"))  # “a few” by default

logging.getLogger("alembic.runtime.migration").setLevel(getattr(logging, LOG_LVL, logging.INFO))
engine_logger = logging.getLogger("sqlalchemy.engine")
engine_logger.setLevel(logging.INFO if LOG_SQL else getattr(logging, LOG_LVL, logging.INFO))

# ---- Tables ------------------------------------------------------------------
STUDENTS_TBL = "students"
WAIVERS_TBL  = "waivers"

# ---- Helpers -----------------------------------------------------------------
def _qt(table: str) -> str:
    return f"{SCHEMA}.{table}" if SCHEMA else table

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

def _dec2(v) -> Decimal | None:
    if v is None: return None
    try:
        if isinstance(v, Decimal):
            q = v
        else:
            s = str(v).strip().replace(",", "")
            if s == "": return None
            if s.startswith("$"): s = s[1:]
            q = Decimal(s)
    except (InvalidOperation, ValueError):
        return None
    return q.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

def _parse_date(v) -> date | None:
    if v is None: return None
    s = str(v).strip()
    if not s: return None
    try:
        # accept YYYY-MM-DD or full ISO datetime; take the date portion
        return datetime.fromisoformat(s).date() if "T" in s or " " in s else date.fromisoformat(s)
    except Exception:
        return None

def _default_csv_path() -> Path:
    envp = os.getenv(CSV_ENV)
    if envp:
        p = Path(envp)
        return (p / CSV_NAME) if p.is_dir() else p
    return Path(__file__).resolve().with_name(CSV_NAME)

def _write_csv(bind, insp) -> Path:
    """(Re)create waiver.csv from a sample of students each run."""
    out = _default_csv_path()
    out.parent.mkdir(parents=True, exist_ok=True)

    # pull student ids
    rows = bind.execute(sa.text(f"SELECT id FROM {_qt(STUDENTS_TBL)} ORDER BY id")).fetchall()
    student_ids = [str(r[0]) for r in rows]
    if not student_ids:
        raise RuntimeError(f"[{revision}] No students found; cannot generate {CSV_NAME}")

    rng_seed = os.getenv("WVR_SEED")
    rng = random.Random(rng_seed)

    n = min(MAX_ROWS, len(student_ids))
    sample = rng.sample(student_ids, n) if len(student_ids) >= n else student_ids

    reasons = [
        "Financial hardship", "Merit-based waiver", "Administrative adjustment",
        "Fee error correction", "Special program", "Needs-based waiver"
    ]
    amounts = [Decimal("25.00"), Decimal("50.00"), Decimal("75.00"), Decimal("100.00"), Decimal("125.00")]
    today = date.today()

    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["student_id","reason","amount","granted_on"])
        for sid in sample:
            reason = rng.choice(reasons)
            amount = rng.choice(amounts)
            granted = today - timedelta(days=rng.randint(0, 120))
            w.writerow([sid, reason, f"{amount:.2f}", granted.isoformat()])

    log.info("[%s] regenerated %s with %d rows -> %s", revision, CSV_NAME, n, out)
    return out

def _open_csv(csv_path: Path):
    f = csv_path.open("r", encoding="utf-8", newline="")
    reader = csv.DictReader(f)
    log.info("[%s] CSV headers: %s (path=%s)", revision, reader.fieldnames, csv_path)
    return reader, f

def _insert_sql(bind):
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns(WAIVERS_TBL, schema=INSPECT_SCHEMA)}
    ins_cols, vals = ["id"], ["gen_random_uuid()"]

    def add(col):
        if col in cols:
            ins_cols.append(col); vals.append(f":{col}")

    for c in ("student_id","reason","amount","granted_on"):
        add(c)
    if "created_at" in cols: ins_cols.append("created_at"); vals.append("now()")
    if "updated_at" in cols: ins_cols.append("updated_at"); vals.append("now()")

    sql = sa.text(f"INSERT INTO {_qt(WAIVERS_TBL)} ({', '.join(ins_cols)}) VALUES ({', '.join(vals)})")
    return sql

# ---- Migration ---------------------------------------------------------------
def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    # Always (re)generate the CSV
    csv_path = _write_csv(bind, insp)
    reader, fobj = _open_csv(csv_path)

    insert_stmt = _insert_sql(bind)

    total = inserted = skipped = 0
    try:
        with _outer_tx(bind):
            for idx, raw in enumerate(reader, start=1):
                total += 1
                row = { (k if not isinstance(k, str) else k.strip()): (v.strip() if isinstance(v, str) else v)
                        for k, v in (raw or {}).items() }

                student_id = row.get("student_id") or None
                if not student_id:
                    skipped += 1
                    log.warning("[%s] row %d missing student_id — skipping", revision, idx)
                    continue

                params = {
                    "student_id": student_id,
                    "reason": (row.get("reason") or None),
                    "amount": _dec2(row.get("amount")),
                    "granted_on": _parse_date(row.get("granted_on")),
                }

                if LOG_ROWS:
                    log.info("[%s] row %d params=%r", revision, idx, params)

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

    log.info("[%s] waivers: CSV rows=%d, inserted=%d, skipped=%d [csv=%s, schema=%s, inspect_schema=%r]",
             revision, total, inserted, skipped, csv_path, SCHEMA, INSPECT_SCHEMA)

    if ABORT_IF_ZERO and inserted == 0:
        raise RuntimeError(f"[{revision}] No rows inserted; enable WVR_LOG_ROWS=1 for per-row details.")

def downgrade() -> None:
    # Non-destructive: keep inserted waivers. If needed, implement CSV-driven delete here.
    pass