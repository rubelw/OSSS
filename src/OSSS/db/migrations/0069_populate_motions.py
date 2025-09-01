"""Populate work_order_parts from CSV (flex headers + robust parsing + FK preflight + loud logging)."""

from __future__ import annotations
import os, csv, logging, re, secrets, json
from pathlib import Path
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from contextlib import nullcontext
from itertools import cycle
from sqlalchemy.dialects import postgresql as pg

from alembic import op
import sqlalchemy as sa

# ---- Alembic identifiers ----
revision = "0067_populate_agenda_items"
down_revision = "0066_populate_webhooks"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")


# ---- Env / toggles -----------------------------------------------------------
LOG_LVL       = os.getenv("MOT_LOG_LEVEL", "DEBUG").upper()
LOG_SQL       = os.getenv("MOT_LOG_SQL", "1") == "1"
LOG_ROWS      = os.getenv("MOT_LOG_ROWS", "1") == "1"
ABORT_IF_ZERO = os.getenv("MOT_ABORT_IF_ZERO", "1") == "1"
SCHEMA        = (os.getenv("MOT_SCHEMA", "public") or "").strip()

CSV_ENV   = "MOTIONS_CSV_PATH"            # dir or explicit file path
CSV_NAME  = "motions.csv"
MAX_ROWS  = int(os.getenv("MOT_ROWS", "100"))   # cap motions generated per run
SEED      = os.getenv("MOT_SEED")               # set for deterministic output

logging.getLogger("alembic.runtime.migration").setLevel(getattr(logging, LOG_LVL, logging.INFO))
engine_logger = logging.getLogger("sqlalchemy.engine")
engine_logger.setLevel(logging.INFO if LOG_SQL else getattr(logging, LOG_LVL, logging.INFO))

# ---- Tables ------------------------------------------------------------------
AGENDA_TBL = "agenda_items"
USERS_TBL  = "users"
MOTIONS_TBL= "motions"

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

def _default_csv_path() -> Path:
    envp = os.getenv(CSV_ENV)
    if envp:
        p = Path(envp)
        return (p / CSV_NAME) if p.is_dir() else p
    return Path(__file__).resolve().with_name(CSV_NAME)

def _csv_path_here() -> Path:
    return Path(__file__).resolve().with_name(CSV_NAME)


def _write_csv(bind) -> Path:
    out = _csv_path_here()
    out.parent.mkdir(parents=True, exist_ok=True)

    # fetch candidates
    ai_ids = [str(r[0]) for r in bind.execute(sa.text("SELECT id FROM public.agenda_items ORDER BY id")).fetchall()]
    user_ids = [str(r[0]) for r in bind.execute(sa.text("SELECT id FROM public.users ORDER BY id")).fetchall()]

    headers = ["agenda_item_id","text","moved_by_id","seconded_by_id","passed","tally_for","tally_against","tally_abstain"]

    # If we don’t have agenda items, write header only and return.
    if not ai_ids:
        log.warning("[%s] No agenda_items found; writing header-only %s and skipping population.", revision, CSV_NAME)
        with out.open("w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(headers)
        return out

    import random
    rng = random.Random(os.getenv("MOT_SEED"))
    rows = int(os.getenv("MOT_ROWS", "50"))

    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(headers)
        for _ in range(rows):
            ai = rng.choice(ai_ids)
            moved = rng.choice(user_ids) if user_ids else None
            second = rng.choice(user_ids) if user_ids else None
            passed = rng.choice([None, True, False])
            tf = rng.randint(0, 7) if passed is not None else None
            ta = rng.randint(0, 7) if passed is not None else None
            tab = rng.randint(0, 3) if passed is not None else None
            text_val = "Motion: " + rng.choice([
                "approve budget", "amend agenda", "extend meeting time",
                "adopt policy", "table item"
            ])
            w.writerow([ai, text_val, moved, second, passed, tf, ta, tab])

    log.info("[%s] wrote motions CSV -> %s", revision, out)
    return out

def _open_csv(csv_path: Path):
    f = csv_path.open("r", encoding="utf-8", newline="")
    reader = csv.DictReader(f)
    log.info("[%s] CSV headers: %s (path=%s)", revision, reader.fieldnames, csv_path)
    return reader, f

def _insert_sql(bind):
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns(_qt(MOTIONS_TBL))}
    ins_cols, vals = ["id"], ["gen_random_uuid()"]

    def add(col):
        if col in cols:
            ins_cols.append(col); vals.append(f":{col}")

    for c in ("agenda_item_id","text","moved_by_id","seconded_by_id","passed","tally_for","tally_against","tally_abstain"):
        add(c)
    if "created_at" in cols: ins_cols.append("created_at"); vals.append("now()")
    if "updated_at" in cols: ins_cols.append("updated_at"); vals.append("now()")

    return sa.text(f"INSERT INTO {_qt(MOTIONS_TBL)} ({', '.join(ins_cols)}) VALUES ({', '.join(vals)})")

def _as_bool(v):
    if v is None: return None
    if isinstance(v, bool): return v
    s = str(v).strip().lower()
    if s in {"true","t","1","yes","y"}: return True
    if s in {"false","f","0","no","n"}: return False
    return None

def _as_int(v):
    if v is None or str(v).strip() == "": return None
    try:
        return int(str(v).strip())
    except Exception:
        return None

# ---- Migration ---------------------------------------------------------------
def upgrade() -> None:
    bind = op.get_bind()
    if LOG_SQL:
        logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)

    csv_path = _write_csv(bind)

    # Open and peek for data rows
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        log.warning("[%s] %s has no data rows (header only). Motions will not be populated.", revision, csv_path)
        if ABORT_IF_ZERO:
            raise RuntimeError(f"[{revision}] No rows to insert into motions and MOT_ABORT_IF_ZERO=1")
        return

    # Build INSERT and insert rows (example; adapt to your existing insert code)
    cols = {c["name"] for c in sa.inspect(bind).get_columns("motions")}
    ins_cols, vals = ["id"], ["gen_random_uuid()"]

    def add(c):
        if c in cols:
            ins_cols.append(c); vals.append(f":{c}")

    for c in ("agenda_item_id","text","moved_by_id","seconded_by_id","passed","tally_for","tally_against","tally_abstain"):
        add(c)
    if "created_at" in cols: ins_cols.append("created_at"); vals.append("now()")
    if "updated_at" in cols: ins_cols.append("updated_at"); vals.append("now()")

    insert_stmt = sa.text(f"INSERT INTO motions ({', '.join(ins_cols)}) VALUES ({', '.join(vals)})")

    inserted = skipped = 0
    with bind.begin():
        for i, r in enumerate(rows, 1):
            params = {
                "agenda_item_id": r.get("agenda_item_id") or None,
                "text": r.get("text") or None,
                "moved_by_id": r.get("moved_by_id") or None,
                "seconded_by_id": r.get("seconded_by_id") or None,
                "passed": (None if (r.get("passed") in (None, "", "None")) else (r.get("passed").lower() == "true")),
                "tally_for": (None if (r.get("tally_for") in (None, "")) else int(r["tally_for"])),
                "tally_against": (None if (r.get("tally_against") in (None, "")) else int(r["tally_against"])),
                "tally_abstain": (None if (r.get("tally_abstain") in (None, "")) else int(r["tally_abstain"])),
            }
            try:
                bind.execute(insert_stmt, params)
                inserted += 1
            except Exception:
                skipped += 1
                log.exception("[%s] row %d failed to insert; params=%r", revision, i, params)

    log.info("[%s] motions inserted=%d, skipped=%d (csv=%s)", revision, inserted, skipped, csv_path)
    if ABORT_IF_ZERO and inserted == 0:
        raise RuntimeError(f"[{revision}] No rows inserted into motions (MOT_ABORT_IF_ZERO=1).")

def downgrade() -> None:
    # Non-destructive; keep data inserted. If needed, implement a CSV-driven delete here.
    pass