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
revision = "0060_populate_plans"
down_revision = "0059_populate_grade_lvl"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

# ---- Env toggles ----
LOG_LVL = os.getenv("PLANS_LOG_LEVEL", "INFO").upper()
LOG_ROWS = os.getenv("PLANS_LOG_ROWS", "0") == "1"
ABORT_IF_ZERO = os.getenv("PLANS_ABORT_IF_ZERO", "0") == "1"

logging.getLogger("alembic.runtime.migration").setLevel(getattr(logging, LOG_LVL, logging.INFO))
logging.getLogger("sqlalchemy.engine").setLevel(getattr(logging, LOG_LVL, logging.INFO))

PLANS_TBL = "plans"
ORGS_TBL  = "organizations"

CSV_NAME  = "plans.csv"

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
        if p and str(p) and p.exists():
            log.info("[%s] using CSV: %s", revision, p)
            return p
    log.warning("[%s] CSV %s not found in standard locations", revision, name)
    return None

def _open_csv(csv_path: Path):
    f = csv_path.open("r", encoding="utf-8", newline="")
    return csv.DictReader(f), f

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

def _uuid_sql(bind) -> str:
    for name in ("gen_random_uuid", "uuid_generate_v4"):
        try:
            if bind.execute(sa.text("SELECT 1 FROM pg_proc WHERE proname=:n"), {"n": name}).scalar():
                log.info("[%s] using %s()", revision, name)
                return f"{name}()"
        except Exception:
            pass
    log.warning("[%s] no native UUID helper found; assuming gen_random_uuid()", revision)
    return "gen_random_uuid()"

def _parse_date(v: str | None):
    if not v: return None
    v = v.strip()
    if not v: return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y/%m/%d"):
        try:
            return date.fromisoformat(v) if fmt == "%Y-%m-%d" else datetime.strptime(v, fmt).date()
        except Exception:
            continue
    return None

def _table_count(bind, table: str) -> int:
    try:
        return int(bind.execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar() or 0)
    except Exception:
        log.exception("[%s] failed to count rows for table %s", revision, table)
        return -1

def _resolve_org_id(bind, insp, raw: str | None):
    """Resolve CSV/org_ref/env into organizations.id (UUID)."""
    if not raw:
        return None, "empty-org-ref"
    val = raw.strip()
    # 1) UUID direct
    try:
        import uuid as _uuid
        _ = _uuid.UUID(val)
        q = sa.text(f"SELECT id FROM {ORGS_TBL} WHERE id = :vid LIMIT 1")
        oid = bind.execute(q, {"vid": val}).scalar()
        if oid:
            return str(oid), "by-id"
    except Exception:
        pass

    # Column discovery
    org_cols = {c["name"] for c in insp.get_columns(ORGS_TBL)}
    candidates = [c for c in ("code","external_id","ext_id","short_code","org_code","number","slug") if c in org_cols]

    # 2) exact match on candidate text-ish ids
    for col in candidates:
        try:
            q = sa.text(f"SELECT id FROM {ORGS_TBL} WHERE {col} = :v LIMIT 1")
            oid = bind.execute(q, {"v": val}).scalar()
            if oid:
                return str(oid), f"by-{col}"
        except Exception:
            log.exception("[%s] org lookup by %s failed", revision, col)

    # 3) by name (case-insensitive)
    if "name" in org_cols:
        try:
            q = sa.text(f"SELECT id FROM {ORGS_TBL} WHERE lower(name) = :v LIMIT 1")
            oid = bind.execute(q, {"v": val.lower()}).scalar()
            if oid:
                return str(oid), "by-name"
        except Exception:
            log.exception("[%s] org lookup by name failed", revision)

    return None, "not-found"

def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    existing = set(insp.get_table_names(schema=None))
    for t in (PLANS_TBL, ORGS_TBL):
        if t not in existing:
            log.warning("[%s] table %r missing — abort.", revision, t)
            return

    csv_path = _find_csv(CSV_NAME, envvar="PLANS_CSV_PATH")
    if not csv_path:
        raise RuntimeError(f"[{revision}] {CSV_NAME} not found")

    pre = _table_count(bind, PLANS_TBL)

    # detect created_at/updated_at
    plan_cols = {c["name"] for c in insp.get_columns(PLANS_TBL)}
    has_created = "created_at" in plan_cols
    has_updated = "updated_at" in plan_cols

    uuid_sql = _uuid_sql(bind)

    # dynamic insert
    ins_cols = ["id", "org_id", "name"]
    ins_vals = [uuid_sql, ":org_id", ":name"]
    if "cycle_start" in plan_cols:
        ins_cols.append("cycle_start"); ins_vals.append(":cycle_start")
    if "cycle_end" in plan_cols:
        ins_cols.append("cycle_end"); ins_vals.append(":cycle_end")
    if "status" in plan_cols:
        ins_cols.append("status"); ins_vals.append(":status")
    if has_created:
        ins_cols.append("created_at"); ins_vals.append("now()")
    if has_updated:
        ins_cols.append("updated_at"); ins_vals.append("now()")

    ins_sql = f"INSERT INTO {PLANS_TBL} ({', '.join(ins_cols)}) VALUES ({', '.join(ins_vals)}) RETURNING id"
    ins = sa.text(ins_sql)

    chk = sa.text(f"SELECT 1 FROM {PLANS_TBL} WHERE org_id=:oid AND lower(name)=:nm LIMIT 1")

    # env org ref default
    default_org_ref = os.getenv("PLANS_ORG_REF", "05400000")

    inserted = skipped = missing_org = 0
    total = 0

    reader, fobj = _open_csv(csv_path)
    try:
        log.info("[%s] CSV header: %s", revision, reader.fieldnames)
        with _outer_tx(bind):
            for idx, raw in enumerate(reader, start=1):
                total += 1
                name = (raw.get("name") or "").strip()
                cycle_start = _parse_date(raw.get("cycle_start"))
                cycle_end   = _parse_date(raw.get("cycle_end"))
                status      = (raw.get("status") or "").strip() or None
                org_ref     = (raw.get("org_ref") or default_org_ref or "").strip()

                if LOG_ROWS:
                    log.info("[%s] row %d raw=%r", revision, idx, raw)

                if not name:
                    log.warning("[%s] row %d: missing plan name; skipping", revision, idx); continue

                org_id, how = _resolve_org_id(bind, insp, org_ref)
                if not org_id:
                    log.warning("[%s] row %d: could not resolve org_id from org_ref=%r (mode=%s); skipping", revision, idx, org_ref, how)
                    missing_org += 1
                    continue

                # idempotence
                if bind.execute(chk, {"oid": org_id, "nm": name.lower()}).scalar():
                    skipped += 1
                    if LOG_ROWS:
                        log.info("[%s] row %d: exists (org_id=%s name=%r)", revision, idx, org_id, name)
                    continue

                params = {"org_id": org_id, "name": name, "cycle_start": cycle_start, "cycle_end": cycle_end, "status": status}

                try:
                    with _per_row_tx(bind):
                        rid = bind.execute(ins, params).scalar()
                        log.info("[%s] row %d: inserted id=%s org_id=%s name=%r dates=%s→%s status=%r", revision, idx, rid, org_id, name, cycle_start, cycle_end, status)
                        inserted += 1
                except Exception:
                    log.exception("[%s] row %d failed to insert; params=%r", revision, idx, params)
    finally:
        try: fobj.close()
        except Exception: pass

    post = _table_count(bind, PLANS_TBL)
    delta = (post if isinstance(post, int) else 0) - (pre if isinstance(pre, int) else 0)
    log.info("[%s] totals: rows_in_csv=%d inserted=%d skipped=%d missing_org=%d pre=%s post=%s delta=%s",
             revision, total, inserted, skipped, missing_org, pre, post, delta)

    if ABORT_IF_ZERO and inserted == 0:
        raise RuntimeError(f"[{revision}] No rows inserted; set PLANS_LOG_ROWS=1 and verify org resolution.")

def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if PLANS_TBL not in set(insp.get_table_names(schema=None)):
        log.info("[%s] downgrade: %s table missing; nothing to do.", revision, PLANS_TBL)
        return

    csv_path = _find_csv(CSV_NAME)
    if not csv_path:
        log.warning("[%s] downgrade: %s not found; skipping deletion.", revision, CSV_NAME)
        return

    default_org_ref = os.getenv("PLANS_ORG_REF", "05400000")

    reader, fobj = _open_csv(csv_path)
    try:
        org_id, how = _resolve_org_id(bind, insp, default_org_ref)
        if not org_id:
            log.warning("[%s] downgrade: could not resolve org from %r (mode=%s); aborting delete.", revision, default_org_ref, how)
            return

        names = [ (row.get("name") or "").strip() for row in reader if (row.get("name") or "").strip() ]
        if not names:
            log.info("[%s] downgrade: no names; nothing to delete.", revision); return

        del_sql = sa.text(f"DELETE FROM {PLANS_TBL} WHERE org_id=:oid AND lower(name) = ANY(:names)")
        del_sql = del_sql.bindparams(
            sa.bindparam("oid"),
            sa.bindparam("names", type_=pg.ARRAY(sa.Text())),
        )
        with _outer_tx(bind):
            rc = bind.execute(del_sql, {"oid": org_id, "names": [n.lower() for n in names]}).rowcount
            log.info("[%s] downgrade: deleted %s rows for org_id=%s", revision, rc, org_id)
    finally:
        try: fobj.close()
        except Exception: pass
