from __future__ import annotations

import os, csv, logging, random, re, secrets, hashlib
from pathlib import Path
from contextlib import nullcontext
from datetime import datetime
from itertools import cycle
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from sqlalchemy.dialects import postgresql as pg

from alembic import op
import sqlalchemy as sa

# ---- Alembic identifiers ----
revision = "0071_populate_user_accts"
# If your head before this migration is different, adjust the down_revision accordingly.
down_revision = "0070_populate_votes"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")


# ---- Config / env toggles ----------------------------------------------------
LOG_LVL        = os.getenv("UA_LOG_LEVEL", "INFO").upper()
LOG_SQL        = os.getenv("UA_LOG_SQL", "0") == "1"
LOG_ROWS       = os.getenv("UA_LOG_ROWS", "0") == "1"
ABORT_IF_ZERO  = os.getenv("UA_ABORT_IF_ZERO", "0") == "1"
UA_ROWS        = int(os.getenv("UA_ROWS", "100"))
UA_SEED        = os.getenv("UA_SEED")

CSV_ENV        = "USER_ACCOUNTS_CSV_PATH"
CSV_NAME       = "user_accounts.csv"

logging.getLogger("alembic.runtime.migration").setLevel(getattr(logging, LOG_LVL, logging.INFO))
engine_logger = logging.getLogger("sqlalchemy.engine")
engine_logger.setLevel(logging.INFO if LOG_SQL else getattr(logging, LOG_LVL, logging.INFO))

# ---- Tables ------------------------------------------------------------------
PERSONS_TBL       = "persons"
USER_ACCOUNTS_TBL = "user_accounts"

# ---- Helpers -----------------------------------------------------------------
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

def _default_output_path(name: str) -> Path:
    envp = os.getenv(CSV_ENV)
    if envp:
        p = Path(envp)
        return (p / name) if p.is_dir() else p
    # co-locate with this migration file
    return Path(__file__).resolve().with_name(name)

def _bool_to_str(v: bool) -> str:
    return "1" if v else "0"

def _str_to_bool(v: Optional[str]) -> Optional[bool]:
    if v is None:
        return None
    s = str(v).strip().lower()
    if s in {"1","true","t","yes","y"}:
        return True
    if s in {"0","false","f","no","n"}:
        return False
    return None

def _pbkdf2(password: str, rounds: int = 260000) -> str:
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), rounds)
    return f"pbkdf2_sha256${rounds}${salt}${dk.hex()}"

# ---- CSV creation ------------------------------------------------------------
def _write_csv(bind) -> Path:
    """
    Always (re)write user_accounts.csv with UA_ROWS rows, sampling random person_id
    from the persons table. If no persons exist, write headers only.
    """
    out = _default_output_path(CSV_NAME)
    out.parent.mkdir(parents=True, exist_ok=True)

    person_ids = [str(r[0]) for r in bind.execute(sa.text(f"SELECT id FROM {PERSONS_TBL} ORDER BY id")).fetchall()]
    if not person_ids:
        log.warning("[%s] No persons found; writing header-only %s and skipping population.", revision, out)
        with out.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f); w.writerow(["person_id","username","password_hash","is_active"])
        return out

    rng = random.Random(UA_SEED)
    # ensure we don't exceed available persons (keep 1 account per person by default)
    count = min(UA_ROWS, len(person_ids))
    rng.shuffle(person_ids)
    chosen = person_ids[:count]

    # We will generate deterministic-ish usernames based on id prefix, unique by definition.
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["person_id","username","password_hash","is_active"])
        for pid in chosen:
            uname = f"auto.{pid[:8]}"
            # simple temp password basis; only hash is stored
            phash = _pbkdf2(f"TempPass!{pid[:6]}")
            is_active = rng.random() < 0.9  # 90% active
            w.writerow([pid, uname, phash, _bool_to_str(is_active)])

    log.info("[%s] wrote %d rows -> %s", revision, count, out)
    return out

def _open_csv(csv_path: Path):
    f = csv_path.open("r", encoding="utf-8", newline="")
    reader = csv.DictReader(f)
    log.info("[%s] CSV headers: %s (%s)", revision, reader.fieldnames, csv_path)
    return reader, f

# ---- Insert builder ----------------------------------------------------------
def _insert_sql(bind):
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns(USER_ACCOUNTS_TBL)}

    ins_cols, vals = ["id"], ["gen_random_uuid()"]

    def add(col):
        if col in cols:
            ins_cols.append(col)
            vals.append(f":{col}")

    for c in ("person_id","username","password_hash","is_active"):
        add(c)
    if "created_at" in cols: ins_cols.append("created_at"); vals.append("now()")
    if "updated_at" in cols: ins_cols.append("updated_at"); vals.append("now()")

    # Upsert on username to be idempotent
    sql = sa.text(
        f"INSERT INTO {USER_ACCOUNTS_TBL} ({', '.join(ins_cols)}) "
        f"VALUES ({', '.join(vals)}) "
        f"ON CONFLICT (username) DO NOTHING"
    )
    return sql, cols

# ---- Migration ---------------------------------------------------------------
def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    # Always (re)generate CSV on every run
    csv_path = _write_csv(bind)

    reader, fobj = _open_csv(csv_path)
    insert_stmt, cols = _insert_sql(bind)

    total = inserted = skipped = 0
    try:
        with _outer_tx(bind):
            for idx, raw in enumerate(reader, start=1):
                total += 1
                row = { (k.strip() if isinstance(k,str) else k): (v.strip() if isinstance(v,str) else v)
                        for k, v in (raw or {}).items() }

                person_id     = row.get("person_id") or None
                username      = row.get("username") or None
                password_hash = row.get("password_hash") or None
                is_active     = _str_to_bool(row.get("is_active"))

                if not person_id or not username:
                    skipped += 1
                    if LOG_ROWS:
                        log.warning("[%s] row %d missing person_id/username — skipping: %r", revision, idx, row)
                    continue

                params = {
                    "person_id": person_id,
                    "username": username,
                    "password_hash": password_hash,
                    "is_active": is_active if is_active is not None else True,
                }
                # trim to actual table columns
                params = {k: v for k, v in params.items() if k in cols}

                try:
                    with _per_row_tx(bind):
                        bind.execute(insert_stmt, params)
                        inserted += 1
                        if LOG_ROWS:
                            log.info("[%s] row %d INSERT ok (username=%r)", revision, idx, username)
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
        raise RuntimeError(f"[{revision}] No rows inserted; set UA_LOG_ROWS=1 to see per-row details.")

def downgrade() -> None:
    # Best-effort: delete only rows created by this seed (by our username prefix 'auto.')
    bind = op.get_bind()
    if sa.inspect(bind).has_table(USER_ACCOUNTS_TBL):
        try:
            res = bind.execute(sa.text(
                f"DELETE FROM {USER_ACCOUNTS_TBL} WHERE username LIKE 'auto.%'"
            ))
            try:
                log.info("[%s] downgrade deleted %s seeded rows from %s", revision, res.rowcount, USER_ACCOUNTS_TBL)
            except Exception:
                pass
        except Exception:
            log.exception("[%s] downgrade best-effort delete failed", revision)
