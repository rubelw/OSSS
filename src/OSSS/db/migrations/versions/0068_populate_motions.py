"""Populate motions from CSV (auto-generate CSV each run, robust parsing, no manual transactions)."""

from __future__ import annotations

import os, csv, logging, random
from pathlib import Path
from contextlib import nullcontext
from datetime import datetime

from alembic import op
import sqlalchemy as sa

# ---- Alembic identifiers ----
revision = "0068_populate_motions"
# If your head before this migration is different, adjust the down_revision accordingly.
down_revision = "0067_populate_agenda_items"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

# ---- Config / env toggles ----------------------------------------------------
LOG_LVL        = os.getenv("MOT_LOG_LEVEL", "INFO").upper()
LOG_SQL        = os.getenv("MOT_LOG_SQL", "0") == "1"
LOG_ROWS       = os.getenv("MOT_LOG_ROWS", "0") == "1"
ABORT_IF_ZERO  = os.getenv("MOT_ABORT_IF_ZERO", "0") == "1"

CSV_ENV        = "MOTIONS_CSV_PATH"
CSV_NAME       = "motions.csv"
MOT_ROWS       = int(os.getenv("MOT_ROWS", "40"))
MOT_SEED       = os.getenv("MOT_SEED")

logging.getLogger("alembic.runtime.migration").setLevel(getattr(logging, LOG_LVL, logging.INFO))
engine_logger = logging.getLogger("sqlalchemy.engine")
engine_logger.setLevel(logging.INFO if LOG_SQL else getattr(logging, LOG_LVL, logging.INFO))

# ---- Tables ------------------------------------------------------------------
MOTIONS_TBL = "motions"
AGENDA_TBL  = "agenda_items"
USERS_TBL   = "users"

# ---- Paths -------------------------------------------------------------------
def _default_output_path(name: str) -> Path:
    envp = os.getenv(CSV_ENV)
    if envp:
        p = Path(envp)
        return (p / name) if p.is_dir() else p
    return Path(__file__).resolve().with_name(name)

def _write_csv(bind) -> Path:
    """Recreate motions.csv on every run.
    If there are no agenda_items, write only header and log a note.
    """
    out = _default_output_path(CSV_NAME)
    out.parent.mkdir(parents=True, exist_ok=True)

    agenda_ids = [str(r[0]) for r in bind.execute(sa.text(f"SELECT id FROM {AGENDA_TBL} ORDER BY id")).fetchall()]
    user_ids   = [str(r[0]) for r in bind.execute(sa.text(f"SELECT id FROM {USERS_TBL} ORDER BY id")).fetchall()]

    fields = ["agenda_item_id","text","moved_by_id","seconded_by_id","passed","tally_for","tally_against","tally_abstain"]
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(fields)
        if not agenda_ids:
            log.warning("[%s] No agenda_items found; writing header-only %s and skipping population.", revision, out)
            return out

        rng = random.Random(MOT_SEED)
        for i in range(MOT_ROWS):
            aid = rng.choice(agenda_ids)
            moved = rng.choice(user_ids) if user_ids else ""
            second = rng.choice(user_ids) if (user_ids and rng.random() < 0.7) else ""
            # 60% pass, 25% fail, 15% None
            roll = rng.random()
            if roll < 0.60:
                passed = "true"
                for_votes = rng.randint(3, 9)
                against   = rng.randint(0, 3)
                abstain   = rng.randint(0, 2)
            elif roll < 0.85:
                passed = "false"
                for_votes = rng.randint(0, 3)
                against   = rng.randint(3, 9)
                abstain   = rng.randint(0, 2)
            else:
                passed = ""
                for_votes = against = abstain = ""

            text = f"Auto motion for agenda {aid[:8]} (seeded by 0068)"
            w.writerow([aid, text, moved, second, passed, for_votes, against, abstain])

    log.info("[%s] wrote %d rows -> %s", revision, MOT_ROWS, out)
    return out

def _open_csv(csv_path: Path):
    f = csv_path.open("r", encoding="utf-8", newline="")
    reader = csv.DictReader(f)
    log.info("[%s] CSV headers: %s (%s)", revision, reader.fieldnames, csv_path)
    return reader, f

# ---- SQL helpers -------------------------------------------------------------
def _insert_sql(bind):
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns(MOTIONS_TBL)}
    ins_cols, vals = ["id"], ["gen_random_uuid()"]

    def add(col):
        if col in cols:
            ins_cols.append(col)
            vals.append(f":{col}")

    for c in ("agenda_item_id","text","moved_by_id","seconded_by_id","passed","tally_for","tally_against","tally_abstain"):
        add(c)
    if "created_at" in cols: ins_cols.append("created_at"); vals.append("now()")
    if "updated_at" in cols: ins_cols.append("updated_at"); vals.append("now()")

    sql = sa.text(f"INSERT INTO {MOTIONS_TBL} ({', '.join(ins_cols)}) VALUES ({', '.join(vals)})")
    return sql, cols

def _bool_or_none(v):
    if v is None: return None
    s = str(v).strip().lower()
    if s in ("", "null", "none"): return None
    if s in ("1","true","t","yes","y"): return True
    if s in ("0","false","f","no","n"): return False
    return None

def _int_or_none(v):
    if v is None: return None
    s = str(v).strip()
    if s == "": return None
    try:
        return int(s)
    except ValueError:
        return None

# ---- Migration ---------------------------------------------------------------
def upgrade() -> None:
    bind = op.get_bind()

    # 1) Always (re)generate CSV
    csv_path = _write_csv(bind)

    # 2) Open CSV and prepare insert
    reader, fobj = _open_csv(csv_path)
    insert_stmt, cols = _insert_sql(bind)

    total = inserted = skipped = 0
    try:
        # Do NOT open our own transaction; Alembic manages one for the migration.
        for idx, raw in enumerate(reader, start=1):
            total += 1
            row = { (k.strip() if isinstance(k, str) else k): (v.strip() if isinstance(v, str) else v)
                    for k, v in (raw or {}).items() }

            agenda_item_id = row.get("agenda_item_id") or None
            text           = row.get("text") or None

            if not agenda_item_id or not text:
                skipped += 1
                if LOG_ROWS:
                    log.warning("[%s] row %d missing agenda_item_id/text — skipping: %r", revision, idx, row)
                continue

            params = {
                "agenda_item_id": agenda_item_id,
                "text": text,
                "moved_by_id": (row.get("moved_by_id") or None) if row.get("moved_by_id") else None,
                "seconded_by_id": (row.get("seconded_by_id") or None) if row.get("seconded_by_id") else None,
                "passed": _bool_or_none(row.get("passed")),
                "tally_for": _int_or_none(row.get("tally_for")),
                "tally_against": _int_or_none(row.get("tally_against")),
                "tally_abstain": _int_or_none(row.get("tally_abstain")),
            }
            # Trim to actual table columns
            params = {k: v for k, v in params.items() if k in cols}

            try:
                bind.execute(insert_stmt, params)
                inserted += 1
                if LOG_ROWS:
                    log.info("[%s] row %d INSERT ok (agenda_item_id=%s)", revision, idx, agenda_item_id)
            except Exception:
                skipped += 1
                log.exception("[%s] row %d INSERT failed; params=%r", revision, idx, params)

    finally:
        try:
            fobj.close()
        except Exception:
            pass

    log.info("[%s] CSV rows=%d, inserted=%d, skipped=%d (file=%s)", revision, total, inserted, skipped, csv_path)
    if ABORT_IF_ZERO and inserted == 0:
        raise RuntimeError(f"[{revision}] No rows inserted; set MOT_LOG_ROWS=1 to see per-row details.")

def downgrade() -> None:
    # Best-effort: remove only rows that look like we seeded them.
    bind = op.get_bind()
    try:
        res = bind.execute(sa.text(
            f"DELETE FROM {MOTIONS_TBL} WHERE text LIKE 'Auto motion for agenda % (seeded by 0068)%'"
        ))
        try:
            log.info("[%s] downgrade deleted %s seeded rows from %s", revision, res.rowcount, MOTIONS_TBL)
        except Exception:
            pass
    except Exception:
        log.exception("[%s] downgrade best-effort delete failed", revision)
