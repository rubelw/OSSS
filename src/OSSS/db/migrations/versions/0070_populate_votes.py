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
revision = "0070_populate_votes"
# If your head before this migration is different, adjust the down_revision accordingly.
down_revision = "0069_populate_webhooks"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")


# ---- Env toggles -------------------------------------------------------------
LOG_LVL        = os.getenv("VOTE_LOG_LEVEL", "INFO").upper()
LOG_SQL        = os.getenv("VOTE_LOG_SQL", "0") == "1"
LOG_ROWS       = os.getenv("VOTE_LOG_ROWS", "0") == "1"
ABORT_IF_ZERO  = os.getenv("VOTE_ABORT_IF_ZERO", "0") == "1"

# Generation knobs
VOTE_MAX_PER_MOTION = int(os.getenv("VOTE_MAX_PER_MOTION", "7"))   # upper bound per motion (<= #users)
VOTE_MIN_PER_MOTION = int(os.getenv("VOTE_MIN_PER_MOTION", "3"))   # lower bound per motion (>=1)
VOTE_SEED           = os.getenv("VOTE_SEED")                        # deterministic when set

CSV_ENV   = "VOTES_CSV_PATH"
CSV_NAME  = "votes.csv"

logging.getLogger("alembic.runtime.migration").setLevel(getattr(logging, LOG_LVL, logging.INFO))
engine_logger = logging.getLogger("sqlalchemy.engine")
engine_logger.setLevel(logging.INFO if LOG_SQL else getattr(logging, LOG_LVL, logging.INFO))

# ---- Tables ------------------------------------------------------------------
VOTES_TBL   = "votes"
MOTIONS_TBL = "motions"
USERS_TBL   = "users"

# ---- Helpers -----------------------------------------------------------------
def _outer_tx(conn):
    """Use a top-level transaction only if one isn't already active."""
    try:
        if hasattr(conn, "get_transaction") and conn.get_transaction() is not None:
            return nullcontext()
        if hasattr(conn, "in_transaction") and conn.in_transaction():
            return nullcontext()
    except Exception:
        return nullcontext()
    return conn.begin()

def _per_row_tx(conn):
    """Nested transaction for row-level isolation when supported."""
    try:
        return conn.begin_nested()
    except Exception:
        return nullcontext()

def _default_output_path(name: str) -> Path:
    envp = os.getenv(CSV_ENV)
    if envp:
        p = Path(envp)
        return (p / name) if p.is_dir() else p
    # co-locate with this migration file
    return Path(__file__).resolve().with_name(name)

def _fetch_ids(bind, table: str) -> list[str]:
    rows = bind.execute(sa.text(f"SELECT id FROM {table} ORDER BY id")).fetchall()
    return [str(r[0]) for r in rows]

def _write_csv(bind) -> Path:
    """Always (re)generate votes.csv. If motions/users are missing, write header-only."""
    out = _default_output_path(CSV_NAME)
    out.parent.mkdir(parents=True, exist_ok=True)

    motion_ids = _fetch_ids(bind, MOTIONS_TBL)
    user_ids   = _fetch_ids(bind, USERS_TBL)

    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["motion_id","voter_id","value"])

        if not motion_ids or not user_ids:
            if not motion_ids:
                log.warning("[%s] No motions found; writing header-only %s", revision, out)
            if not user_ids:
                log.warning("[%s] No users found; writing header-only %s", revision, out)
            # header-only file
            return out

        rng = random.Random(VOTE_SEED)
        # clamp bounds
        max_per = max(1, min(VOTE_MAX_PER_MOTION, len(user_ids)))
        min_per = max(1, min(VOTE_MIN_PER_MOTION, max_per))

        values = ["for", "against", "abstain"]
        weights = [0.6, 0.25, 0.15]  # bias toward "for"

        total_rows = 0
        for mid in motion_ids:
            n = rng.randint(min_per, max_per)
            # sample without replacement
            voters = rng.sample(user_ids, k=n)
            for uid in voters:
                val = rng.choices(values, weights=weights, k=1)[0]
                w.writerow([mid, uid, val])
                total_rows += 1

    log.info("[%s] wrote %d vote rows -> %s", revision, total_rows, out)
    return out

def _open_csv(csv_path: Path):
    f = csv_path.open("r", encoding="utf-8", newline="")
    reader = csv.DictReader(f)
    log.info("[%s] CSV headers: %s (%s)", revision, reader.fieldnames, csv_path)
    return reader, f

def _insert_sql(bind):
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns(VOTES_TBL)}

    ins_cols, vals = ["id"], ["gen_random_uuid()"]

    def add(col: str):
        if col in cols:
            ins_cols.append(col)
            vals.append(f":{col}")

    for c in ("motion_id","voter_id","value"):
        add(c)
    if "created_at" in cols: ins_cols.append("created_at"); vals.append("now()")
    if "updated_at" in cols: ins_cols.append("updated_at"); vals.append("now()")

    sql = sa.text(f"INSERT INTO {VOTES_TBL} ({', '.join(ins_cols)}) VALUES ({', '.join(vals)})")
    return sql, cols

def _exists_vote(bind, motion_id: str, voter_id: str) -> bool:
    """Idempotency: skip if a vote for (motion_id, voter_id) already exists."""
    q = sa.text(f"SELECT 1 FROM {VOTES_TBL} WHERE motion_id=:m AND voter_id=:u LIMIT 1")
    return bind.execute(q, {"m": motion_id, "u": voter_id}).first() is not None

# ---- Migration ---------------------------------------------------------------
def upgrade() -> None:
    bind = op.get_bind()

    # Regenerate CSV every run
    csv_path = _write_csv(bind)
    reader, fobj = _open_csv(csv_path)

    insert_stmt, cols = _insert_sql(bind)

    # Build FK caches
    motion_ids = set(_fetch_ids(bind, MOTIONS_TBL))
    user_ids   = set(_fetch_ids(bind, USERS_TBL))

    total = inserted = skipped = 0
    try:
        with _outer_tx(bind):
            for idx, raw in enumerate(reader, start=1):
                total += 1
                row = { (k.strip() if isinstance(k, str) else k): (v.strip() if isinstance(v, str) else v)
                        for k, v in (raw or {}).items() }

                mid = row.get("motion_id") or None
                uid = row.get("voter_id") or None
                val = row.get("value") or None

                if not mid or not uid or not val:
                    skipped += 1
                    if LOG_ROWS:
                        log.warning("[%s] row %d missing fields — skipping: %r", revision, idx, row)
                    continue

                if mid not in motion_ids:
                    skipped += 1
                    if LOG_ROWS:
                        log.warning("[%s] row %d motion_id not in DB — skipping: %s", revision, idx, mid)
                    continue

                if uid not in user_ids:
                    skipped += 1
                    if LOG_ROWS:
                        log.warning("[%s] row %d voter_id not in DB — skipping: %s", revision, idx, uid)
                    continue

                if _exists_vote(bind, mid, uid):
                    skipped += 1
                    if LOG_ROWS:
                        log.info("[%s] row %d duplicate vote (motion_id=%s, voter_id=%s) — skipping", revision, idx, mid, uid)
                    continue

                params = {"motion_id": mid, "voter_id": uid, "value": val}
                # trim to actual columns (in case table lacks created_at/updated_at etc.)
                params = {k: v for k, v in params.items() if k in cols}

                try:
                    with _per_row_tx(bind):
                        bind.execute(insert_stmt, params)
                        inserted += 1
                        if LOG_ROWS:
                            log.info("[%s] row %d INSERT ok (%s, %s, %s)", revision, idx, mid, uid, val)
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
        raise RuntimeError(f"[{revision}] No rows inserted; set VOTE_LOG_ROWS=1 for per-row details.")

def downgrade() -> None:
    """Best-effort: delete rows that match the current CSV (idempotent cleanup)."""
    bind = op.get_bind()
    csv_path = _default_output_path(CSV_NAME)
    if not csv_path.exists():
        log.info("[%s] downgrade: %s not found; nothing to delete.", revision, csv_path)
        return

    reader, fobj = _open_csv(csv_path)
    pairs: list[tuple[str, str]] = []

    try:
        for row in reader:
            mid = row.get("motion_id") or None
            uid = row.get("voter_id") or None
            val = row.get("value") or None
            if mid and uid and val:
                pairs.append((mid, uid))
    finally:
        try:
            fobj.close()
        except Exception:
            pass

    if not pairs:
        log.info("[%s] downgrade: CSV had no data rows; nothing to delete.", revision)
        return

    # delete by (motion_id, voter_id)
    bind.execute(
        sa.text(f"DELETE FROM {VOTES_TBL} WHERE (motion_id, voter_id) = ANY(:pairs)"),
        {"pairs": pairs},
    )
    log.info("[%s] downgrade: deleted votes for %d (motion_id, voter_id) pairs.", revision, len(pairs))

