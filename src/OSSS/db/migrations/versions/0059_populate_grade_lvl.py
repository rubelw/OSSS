"""Populate pm_work_generators from CSV (robust plan lookup + **extra debug logging** + plan_name→plan_id + deep diagnostics)."""

from __future__ import annotations

import os, csv, logging, re, json
from pathlib import Path
from datetime import datetime
from contextlib import nullcontext
from decimal import Decimal, InvalidOperation

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

# ---- Alembic identifiers ----
revision = "0059_populate_grade_lvl"
down_revision = "0058_populate_assignments"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")


LOG_LVL = os.getenv("GL_LOG_LEVEL","INFO").upper()
LOG_ROWS = os.getenv("GL_LOG_ROWS","0") == "1"
ABORT_IF_ZERO = os.getenv("GL_ABORT_IF_ZERO","0") == "1"

logging.getLogger("alembic.runtime.migration").setLevel(getattr(logging, LOG_LVL, logging.INFO))
logging.getLogger("sqlalchemy.engine").setLevel(getattr(logging, LOG_LVL, logging.INFO))

SCHOOLS_TBL = "schools"
DEST_TBL    = "grade_levels"
CSV_NAME    = "grade_levels.csv"

def _find_csv(name: str, envvar: str | None = None) -> Path | None:
    here = Path(__file__).resolve()
    for p in [
        here.with_name(name),
        here.parent / "data" / name,
        here.parent.parent / "data" / name,
        Path(os.getenv(envvar or "", "")),
        Path.cwd() / name,
        Path("/mnt/data") / name,
    ]:
        try:
            if p and str(p) and p.exists():
                log.info("[%s] using CSV: %s", revision, p)
                return p
        except Exception:
            pass
    log.warning("[%s] CSV %s not found in standard locations", revision, name)
    return None

def _uuid_sql(bind) -> str:
    for fn in ("gen_random_uuid","uuid_generate_v4"):
        try:
            if bind.execute(sa.text("SELECT 1 FROM pg_proc WHERE proname=:n"), {"n": fn}).scalar():
                log.info("[%s] using %s()", revision, fn)
                return f"{fn}()"
        except Exception:
            pass
    log.warning("[%s] no UUID helper found; assuming gen_random_uuid()", revision)
    return "gen_random_uuid()"

def _outer_tx(conn):
    try:
        if hasattr(conn, "get_transaction") and conn.get_transaction() is not None:
            return nullcontext()
        if hasattr(conn, "in_transaction") and conn.in_transaction():
            return nullcontext()
    except Exception:
        return nullcontext()
    return conn.begin()

def upgrade() -> None:
    bind = op.get_bind()

    # quick pre-counts
    try:
        pre_cnt = bind.execute(sa.text(f"SELECT COUNT(*) FROM {DEST_TBL}")).scalar()
    except Exception:
        pre_cnt = None

    csv_path = _find_csv(CSV_NAME, envvar="GRADE_LEVELS_CSV_PATH")
    if not csv_path:
        raise RuntimeError(f"[{revision}] {CSV_NAME} not found")

    try:
        with open(csv_path, "r", encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            log.info("[%s] CSV header: %s", revision, reader.fieldnames)

            # Prepare SQL helpers
            uuid_sql = _uuid_sql(bind)

            q_school = sa.text(f"""
                SELECT id FROM {SCHOOLS_TBL}
                WHERE lower(name) = :n
                LIMIT 1
            """)

            # Some installations may not have a unique constraint; be defensive
            q_exists = sa.text(f"""
                SELECT 1 FROM {DEST_TBL}
                WHERE school_id = :sid AND (lower(name) = :name OR ordinal IS NOT DISTINCT FROM :ord)
                LIMIT 1
            """)

            ins = sa.text(f"""
                INSERT INTO {DEST_TBL} (id, school_id, name, ordinal, created_at, updated_at)
                VALUES ({uuid_sql}, :sid, :name, :ord, now(), now())
                RETURNING id
            """)

            inserted = skipped = missing = 0

            with _outer_tx(bind):
                for idx, row in enumerate(reader, start=1):
                    school_name = (row.get("school_name") or "").strip()
                    gl_name     = (row.get("name") or "").strip()
                    ord_raw     = row.get("ordinal")
                    ord_val     = None
                    try:
                        ord_val = int(ord_raw) if ord_raw not in (None, "",) else None
                    except Exception:
                        ord_val = None

                    if LOG_ROWS:
                        log.info("[%s] row %d raw=%r", revision, idx, row)

                    if not school_name or not gl_name:
                        missing += 1
                        log.warning("[%s] row %d missing required fields school_name/name; skipping", revision, idx)
                        continue

                    sid = bind.execute(q_school, {"n": school_name.lower()}).scalar()
                    if not sid:
                        missing += 1
                        log.warning("[%s] row %d school not found: %r", revision, idx, school_name)
                        continue

                    if bind.execute(q_exists, {"sid": sid, "name": gl_name.lower(), "ord": ord_val}).scalar():
                        skipped += 1
                        continue

                    try:
                        res = bind.execute(ins, {"sid": sid, "name": gl_name, "ord": ord_val}).scalar()
                        log.info("[%s] row %d INSERT id=%s school=%s name=%s ord=%s", revision, idx, res, school_name, gl_name, ord_val)
                        inserted += 1
                    except Exception:
                        log.exception("[%s] row %d failed to insert (school=%s name=%s ord=%s)", revision, idx, school_name, gl_name, ord_val)

    finally:
        pass

    # post counts
    try:
        post_cnt = bind.execute(sa.text(f"SELECT COUNT(*) FROM {DEST_TBL}")).scalar()
    except Exception:
        post_cnt = None

    log.info("[%s] summary: inserted=%s skipped=%s missing=%s pre=%s post=%s delta=%s",
             revision, inserted, skipped, missing, pre_cnt, post_cnt,
             (None if (post_cnt is None or pre_cnt is None) else (post_cnt - pre_cnt)))

    if ABORT_IF_ZERO and (inserted or 0) == 0:
        raise RuntimeError(f"[{revision}] No rows inserted; set GL_LOG_ROWS=1 for per-row diagnostics.")

def downgrade() -> None:
    # Best-effort: delete rows that match the CSV (idempotent)
    bind = op.get_bind()
    csv_path = _find_csv(CSV_NAME, envvar="GRADE_LEVELS_CSV_PATH")
    if not csv_path:
        log.warning("[%s] downgrade: CSV not found; nothing to do.", revision)
        return

    q_school = sa.text(f"""
        SELECT id FROM {SCHOOLS_TBL}
        WHERE lower(name) = :n
        LIMIT 1
    """)

    del_sql = sa.text(f"""
        DELETE FROM {DEST_TBL}
        WHERE school_id = :sid AND lower(name) = :name
    """)

    with open(csv_path, "r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        deleted = 0
        for row in reader:
            school_name = (row.get("school_name") or "").strip().lower()
            gl_name = (row.get("name") or "").strip().lower()
            if not school_name or not gl_name:
                continue
            sid = bind.execute(q_school, {"n": school_name}).scalar()
            if not sid:
                continue
            res = bind.execute(del_sql, {"sid": sid, "name": gl_name})
            try:
                rc = res.rowcount
            except Exception:
                rc = None
            deleted += (rc or 0)
        log.info("[%s] downgrade: deleted rows (approx)=%s", revision, deleted)
