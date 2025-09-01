"""Populate pm_work_generators from CSV (robust plan lookup + **extra debug logging** + plan_name→plan_id + deep diagnostics)."""

from __future__ import annotations

import os, csv, logging, re, json, hashlib, time
from pathlib import Path
from datetime import datetime
from contextlib import nullcontext
from decimal import Decimal, InvalidOperation
from collections import defaultdict, namedtuple

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

# ---- Alembic identifiers ----
revision = "0062_populate_users"
down_revision = "0061_populate_work_orders"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")


USERS_TBL = "users"
CSV_NAME  = "users.csv"

# ---- Logging toggles ---------------------------------------------------------
LOG_LVL       = os.getenv("USERS_LOG_LEVEL", "INFO").upper()
LOG_SQL       = os.getenv("USERS_LOG_SQL", "0") == "1"
LOG_ROWS      = os.getenv("USERS_LOG_ROWS", "0") == "1"
ABORT_IF_ZERO = os.getenv("USERS_ABORT_IF_ZERO", "0") == "1"

logging.getLogger("alembic").setLevel(getattr(logging, LOG_LVL, logging.INFO))
logging.getLogger("alembic.runtime.migration").setLevel(getattr(logging, LOG_LVL, logging.INFO))
logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO if LOG_SQL else getattr(logging, LOG_LVL, logging.WARNING))

# ---- Helpers -----------------------------------------------------------------
def _has_column(insp: sa.Inspector, table: str, col: str) -> bool:
    try:
        return any(c["name"] == col for c in insp.get_columns(table))
    except Exception:
        return False

def _find_csv(name: str) -> Path | None:
    here = Path(__file__).resolve()
    candidates = [
        here.with_name(name),
        here.parent / "data" / name,
        here.parent.parent / "data" / name,
        Path.cwd() / name,
        Path("/mnt/data") / name,
        Path(os.getenv("USERS_CSV_PATH", "")),
    ]
    for p in candidates:
        if p and str(p) and p.exists():
            log.info("[%s] using CSV: %s", revision, p)
            return p
    log.warning("[%s] CSV %s not found in standard locations", revision, name)
    return None

def _parse_dt(val):
    if not val or not str(val).strip():
        return None
    s = str(val).strip()
    try:
        # tolerate trailing Z
        if s.endswith("Z"):
            s = s[:-1]
        return datetime.fromisoformat(s)
    except Exception:
        return None

# ---- Core --------------------------------------------------------------------
def _ensure_updated_at(bind, insp):
    if not _has_column(insp, USERS_TBL, "updated_at"):
        log.info("[%s] Adding %s.updated_at (TIMESTAMPTZ NOT NULL DEFAULT now())", revision, USERS_TBL)
        op.add_column(
            USERS_TBL,
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
        )
        bind.execute(sa.text(f"UPDATE {USERS_TBL} SET updated_at = COALESCE(updated_at, created_at, now())"))
    # trigger to keep updated_at fresh
    op.execute("""
    CREATE OR REPLACE FUNCTION set_timestamp()
    RETURNS trigger AS $$
    BEGIN
      NEW.updated_at = now();
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """)
    op.execute(f"""
    DO $$
    BEGIN
      IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'users_set_timestamp') THEN
        CREATE TRIGGER users_set_timestamp
        BEFORE UPDATE ON {USERS_TBL}
        FOR EACH ROW EXECUTE FUNCTION set_timestamp();
      END IF;
    END $$;
    """)

def _insert_users_from_csv(bind, insp):
    # confirm columns that actually exist
    cols = {c["name"] for c in insp.get_columns(USERS_TBL)}
    need_created_at = "created_at" in cols

    csv_path = _find_csv(CSV_NAME)
    if not csv_path:
        log.warning("[%s] users CSV not found; skipping population step", revision)
        return 0, 0, 0

    inserted = skipped = updated = 0
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        rdr = csv.DictReader(f)
        if not rdr.fieldnames:
            log.warning("[%s] users CSV has no header; nothing to do", revision)
            return 0, 0, 0

        # Minimal required fields
        has_username = "username" in [h.strip() for h in rdr.fieldnames]
        has_email    = "email"    in [h.strip() for h in rdr.fieldnames]
        if not (has_username and has_email):
            log.error("[%s] users CSV must have 'username' and 'email' columns; got: %s", revision, rdr.fieldnames)
            return 0, 0, 0

        # Build parametrized INSERT with ON CONFLICT DO NOTHING
        if need_created_at:
            sql = sa.text(f"""
                INSERT INTO {USERS_TBL} (id, username, email, created_at)
                VALUES (gen_random_uuid(), :username, :email, COALESCE(:created_at, now()))
                ON CONFLICT DO NOTHING
            """)
        else:
            sql = sa.text(f"""
                INSERT INTO {USERS_TBL} (id, username, email)
                VALUES (gen_random_uuid(), :username, :email)
                ON CONFLICT DO NOTHING
            """)

        # Optional gentle “upsert” for email if username exists but email differs (rare path)
        can_update = "username" in cols and "email" in cols
        upd = sa.text(f"UPDATE {USERS_TBL} SET email = :email WHERE username = :username AND email IS DISTINCT FROM :email")

        for i, raw in enumerate(rdr, start=1):
            username = (raw.get("username") or "").strip()
            email    = (raw.get("email") or "").strip()
            c_at     = _parse_dt(raw.get("created_at"))

            if not username or not email:
                skipped += 1
                if LOG_ROWS:
                    log.warning("[%s] row %d skipped: missing username or email (%r, %r)", revision, i, username, email)
                continue

            params = {"username": username, "email": email}
            if need_created_at:
                params["created_at"] = c_at

            try:
                res = bind.execute(sql, params)
                if res.rowcount and res.rowcount > 0:
                    inserted += 1
                    if LOG_ROWS:
                        log.info("[%s] row %d INSERT ok: %s", revision, i, username)
                else:
                    # existed (conflict) — optionally update email to match CSV
                    if can_update:
                        ures = bind.execute(upd, params)
                        if ures.rowcount and ures.rowcount > 0:
                            updated += 1
                            if LOG_ROWS:
                                log.info("[%s] row %d UPDATE email ok: %s", revision, i, username)
                        else:
                            if LOG_ROWS:
                                log.info("[%s] row %d exists; no change: %s", revision, i, username)
                    else:
                        if LOG_ROWS:
                            log.info("[%s] row %d exists; no change: %s", revision, i, username)
            except Exception:
                skipped += 1
                log.exception("[%s] row %d failed; data=%r", revision, i, params)

    return inserted, updated, skipped

# ---- Migration entrypoints ---------------------------------------------------
def upgrade() -> None:
    t0 = time.perf_counter()
    bind = op.get_bind()
    insp = sa.inspect(bind)

    log.info("[%s] === BEGIN upgrade ===", revision)
    _ensure_updated_at(bind, insp)

    ins, upd, skip = _insert_users_from_csv(bind, insp)
    log.info("[%s] users.csv results: inserted=%d, updated=%d, skipped=%d", revision, ins, upd, skip)

    if ABORT_IF_ZERO and ins == 0 and upd == 0:
        raise RuntimeError(f"[{revision}] No users inserted/updated. Set USERS_LOG_ROWS=1 for per-row details.")

    log.info("[%s] === END upgrade (%.3fs) ===", revision, time.perf_counter() - t0)

def downgrade() -> None:
    # Best-effort: remove the users we inserted by username from the CSV.
    bind = op.get_bind()
    path = _find_csv(CSV_NAME)
    if not path:
        log.info("[%s] downgrade: CSV not found; skipping user deletions", revision)
    else:
        with path.open("r", encoding="utf-8", newline="") as f:
            rdr = csv.DictReader(f)
            usernames = [ (r.get("username") or "").strip() for r in rdr if r.get("username") ]
        if usernames:
            bind.execute(sa.text(f"DELETE FROM {USERS_TBL} WHERE username = ANY(:u)"), {"u": usernames})
            log.info("[%s] downgrade: deleted %d users by username list", revision, len(usernames))

    # Drop trigger + column to revert schema change
    op.execute("""
    DO $$
    BEGIN
      IF EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'users_set_timestamp') THEN
        DROP TRIGGER users_set_timestamp ON users;
      END IF;
    END $$;
    """)
    insp = sa.inspect(bind)
    if _has_column(insp, USERS_TBL, "updated_at"):
        op.drop_column(USERS_TBL, "updated_at")