"""Populate pm_work_generators from CSV (robust plan lookup + **extra debug logging** + plan_name→plan_id + deep diagnostics)."""

from __future__ import annotations

import os, csv, logging, re, json, hashlib
from pathlib import Path
from datetime import datetime
from contextlib import nullcontext
from decimal import Decimal, InvalidOperation
from collections import defaultdict, namedtuple

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

# ---- Alembic identifiers ----
revision = "0061_populate_work_orders"
down_revision = "0060_populate_plans"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")


# ---- Verbosity toggles (env-driven) ----
LOG_LVL       = os.getenv("WO_LOG_LEVEL", "INFO").upper()
LOG_ROWS      = os.getenv("WO_LOG_ROWS", "0") == "1"
ABORT_IF_ZERO = os.getenv("WO_ABORT_IF_ZERO", "0") == "1"
VERIFY_EVERY  = os.getenv("WO_VERIFY_EVERY", "0") == "1"

logging.getLogger("alembic.runtime.migration").setLevel(getattr(logging, LOG_LVL, logging.INFO))
logging.getLogger("sqlalchemy.engine").setLevel(getattr(logging, LOG_LVL, logging.INFO))

# ---- Table names ----
SCHOOLS_TBL   = "schools"
BUILDINGS_TBL = "buildings"
SPACES_TBL    = "spaces"
REQUESTS_TBL  = "maintenance_requests"
ORDERS_TBL    = "work_orders"

CSV_NAME      = "work_orders.csv"

# ---- Helpers ----------------------------------------------------------------
_norm_ws_re = re.compile(r"\s+")

def _norm(s: str | None) -> str:
    if s is None:
        return ""
    s = s.replace("\\ufeff","").strip().lower()
    return _norm_ws_re.sub(" ", s)

def _none_if_blank(v):
    if v is None: return None
    if isinstance(v, str) and v.strip() == "": return None
    return v

def _parse_dt(v):
    v = _none_if_blank(v)
    if v is None: return None
    if isinstance(v, (datetime,)): return v
    s = str(v).strip()
    try:
        if s.endswith("Z"):
            s = s[:-1]
        return datetime.fromisoformat(s)
    except Exception:
        return None

def _parse_decimal(v):
    v = _none_if_blank(v)
    if v is None: return None
    try:
        return Decimal(str(v))
    except (InvalidOperation, ValueError, TypeError):
        return None

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

def _has_column(insp: sa.Inspector, table: str, col: str) -> bool:
    try:
        return any(c["name"] == col for c in insp.get_columns(table))
    except Exception:
        return False

def _open_csv(csv_path: Path):
    f = csv_path.open("r", encoding="utf-8", newline="")
    reader = csv.DictReader(f)
    return reader, f

# ---- Lookup index builders ---------------------------------------------------
def _build_school_index(bind):
    rows = bind.execute(sa.text(f"SELECT id, name FROM {SCHOOLS_TBL}")).mappings().all()
    ix = {_norm(r["name"]): str(r["id"]) for r in rows if r.get("name")}
    log.info("[%s] schools loaded: %d", revision, len(ix))
    return ix

def _build_building_indexes(bind, insp):
    has_b_school = _has_column(insp, BUILDINGS_TBL, "school_id")
    bldg_by_key: dict[tuple[str|None, str], str] = {}
    names_by_school: dict[str|None, set[str]] = {}

    if has_b_school:
        rows = bind.execute(sa.text(f"SELECT id, school_id, name FROM {BUILDINGS_TBL}")).mappings().all()
        for r in rows:
            key = (str(r["school_id"]) if r.get("school_id") else None, _norm(r.get("name")))
            if key[1]:
                bldg_by_key[key] = str(r["id"])
                names_by_school.setdefault(key[0], set()).add(r["name"] or "")
        log.info("[%s] buildings loaded with school_id: %d", revision, len(bldg_by_key))
    else:
        rows = bind.execute(sa.text(f"SELECT id, name FROM {BUILDINGS_TBL}")).mappings().all()
        for r in rows:
            key = (None, _norm(r.get("name")))
            if key[1]:
                bldg_by_key[key] = str(r["id"])
                names_by_school.setdefault(None, set()).add(r["name"] or "")
        log.info("[%s] buildings loaded w/o school_id: %d", revision, len(bldg_by_key))

    return bldg_by_key, names_by_school, has_b_school

def _build_space_indexes(bind):
    """
    spaces no longer carries building_id; fetch it via floors.
    Use COALESCE(TRIM(name), code) as the display/match name.
    """
    rows = bind.execute(sa.text("""
        SELECT
            s.id          AS space_id,
            f.building_id AS building_id,
            COALESCE(NULLIF(TRIM(s.name), ''), s.code) AS space_name
        FROM spaces s
        LEFT JOIN floors f ON f.id = s.floor_id
    """)).mappings().all()

    space_by_bldg_name: dict[tuple[str, str], str] = {}
    names_by_bldg: dict[str, set[str]] = {}

    for r in rows:
        bid = r["building_id"]
        if bid is None:
            continue
        name = (r["space_name"] or "").strip()
        if not name:
            continue
        bid_s = str(bid)
        norm_name = _norm(name)
        space_by_bldg_name[(bid_s, norm_name)] = str(r["space_id"])
        names_by_bldg.setdefault(bid_s, set()).add(name)

    log.info("[%s] spaces loaded: %d mappings for %d buildings", revision, len(space_by_bldg_name), len(names_by_bldg))
    return space_by_bldg_name, names_by_bldg

def _build_request_index(bind, insp):
    cols = {c["name"] for c in insp.get_columns(REQUESTS_TBL)}
    cand_cols = [c for c in ["description","descriptions","details","summary","title"] if c in cols]
    if not cand_cols:
        log.info("[%s] maintenance_requests: no description-like column found; request lookup disabled.", revision)
        return {}
    q = sa.text(f"SELECT id, {cand_cols[0]} AS desc FROM {REQUESTS_TBL}")
    rows = bind.execute(q).mappings().all()
    ix = {_norm(r["desc"]): str(r["id"]) for r in rows if r.get("desc")}
    log.info("[%s] maintenance_requests loaded: %d (col=%s)", revision, len(ix), cand_cols[0])
    return ix

# ---- Insert builder ----------------------------------------------------------
def _insert_sql(bind, insp):
    cols = {c["name"] for c in insp.get_columns(ORDERS_TBL)}
    ins_cols = ["id"]
    vals = ["gen_random_uuid()"]
    params = {}

    def add(col, param):
        if col in cols:
            ins_cols.append(col)
            vals.append(f":{param}")
            params[param] = None

    add("school_id", "school_id")
    add("building_id","building_id")
    add("space_id","space_id")
    add("request_id","request_id")
    add("status","status")
    add("priority","priority")
    add("category","category")
    add("summary","summary")
    add("description","description")
    add("requested_due_at","requested_due_at")
    add("scheduled_start_at","scheduled_start_at")
    add("scheduled_end_at","scheduled_end_at")
    add("completed_at","completed_at")
    add("assigned_to_user_id","assigned_to_user_id")
    add("materials_cost","materials_cost")
    add("labor_cost","labor_cost")
    add("other_cost","other_cost")
    if "attributes" in cols:
        ins_cols.append("attributes"); vals.append(":attributes"); params["attributes"] = None
    if "created_at" in cols: ins_cols.append("created_at"); vals.append("now()")
    if "updated_at" in cols: ins_cols.append("updated_at"); vals.append("now()")

    sql = sa.text(f"INSERT INTO {ORDERS_TBL} ({', '.join(ins_cols)}) VALUES ({', '.join(vals)}) RETURNING id")
    if "attributes" in params:
        sql = sql.bindparams(sa.bindparam("attributes", type_=pg.JSONB))
    return sql, set(params.keys())

# ---- Migration ---------------------------------------------------------------
def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    csv_path = _find_csv(CSV_NAME, envvar="WORK_ORDERS_CSV_PATH")
    if not csv_path:
        raise RuntimeError(f"[{revision}] {CSV_NAME} not found")

    sch_ix = _build_school_index(bind)
    bldg_ix, bnames_by_school, has_b_school = _build_building_indexes(bind, insp)
    space_ix, space_names_by_bldg = _build_space_indexes(bind)
    req_ix = _build_request_index(bind, insp)

    insert_stmt, param_keys = _insert_sql(bind, insp)

    reader, fobj = _open_csv(csv_path)

    inserted = skipped = 0
    total = 0

    try:
        with _outer_tx(bind):
            for idx, raw in enumerate(reader, start=1):
                total += 1
                row = { (k.strip() if isinstance(k,str) else k): (v.strip() if isinstance(v, str) else v)
                        for k, v in (raw or {}).items() }

                sname = _norm(row.get("school_name"))
                bname = _norm(row.get("building_name"))
                spname= _norm(row.get("space_name"))
                mdesc = _norm(row.get("maintenance_description"))

                school_id = sch_ix.get(sname) if sname else None
                if not school_id:
                    log.warning("[%s] row %d: school not found %r — skipping", revision, idx, row.get("school_name"))
                    skipped += 1; continue

                # building lookup
                bkey = (school_id if has_b_school else None, bname)
                building_id = bldg_ix.get(bkey)
                if not building_id:
                    sugg = sorted(list(bnames_by_school.get(school_id if has_b_school else None, set())))[:5]
                    log.warning("[%s] row %d: building not found %r under school_id=%s; suggestions=%s",
                                revision, idx, row.get("building_name"), school_id if has_b_school else None, sugg)
                    skipped += 1; continue

                # space lookup by (building_id, space_name)
                space_id = space_ix.get((building_id, spname))
                if not space_id:
                    # suggestions(id) list = names for this building_id
                    sugg_names_all = sorted(list(space_names_by_bldg.get(building_id, set())))
                    sugg_names = sugg_names_all[:5]
                    if not sugg_names_all:
                        log.warning("[%s] row %d: space not found %r; no suggestions for building_id=%s (school_id=%s) — skipping",
                                    revision, idx, row.get("space_name"), building_id, school_id)
                        skipped += 1; continue

                    # Deterministic "random" pick from suggestions(id) list
                    token = f"{school_id}|{building_id}|{sname}|{bname}|{spname}|{idx}"
                    h = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16)
                    chosen_name = sugg_names_all[h % len(sugg_names_all)]
                    chosen_norm = _norm(chosen_name)
                    picked_space_id = space_ix.get((building_id, chosen_norm))

                    if not picked_space_id:
                        log.warning("[%s] row %d: space not found %r; suggestions(id)=%s — fallback pick %r did not resolve; skipping",
                                    revision, idx, row.get("space_name"), sugg_names, chosen_name)
                        skipped += 1; continue

                    log.warning("[%s] row %d: space not found %r; suggestions(id)=%s — picked %r",
                                revision, idx, row.get("space_name"), sugg_names, chosen_name)
                    space_id = picked_space_id

                request_id = req_ix.get(mdesc) if mdesc else None

                # sanitize values
                params = {
                    "school_id": school_id,
                    "building_id": building_id,
                    "space_id": space_id,
                    "request_id": request_id,
                    "status": row.get("status") or "open",
                    "priority": _none_if_blank(row.get("priority")),
                    "category": _none_if_blank(row.get("category")),
                    "summary": row.get("summary") or (row.get("maintenance_description") or "Work order"),
                    "description": row.get("description") or row.get("maintenance_description"),
                    "requested_due_at": _parse_dt(row.get("requested_due_at")),
                    "scheduled_start_at": _parse_dt(row.get("scheduled_start_at")),
                    "scheduled_end_at": _parse_dt(row.get("scheduled_end_at")),
                    "completed_at": _parse_dt(row.get("completed_at")),
                    "assigned_to_user_id": _none_if_blank(row.get("assigned_to_user_id")),
                    "materials_cost": _parse_decimal(row.get("materials_cost")),
                    "labor_cost": _parse_decimal(row.get("labor_cost")),
                    "other_cost": _parse_decimal(row.get("other_cost")),
                }

                if "attributes" in param_keys:
                    attrs = row.get("attributes")
                    if isinstance(attrs, str):
                        a = attrs.strip()
                        if a in ("", "null", "NULL", '""', "{}", "[]"):
                            attrs = None
                        else:
                            try:
                                attrs = json.loads(attrs)
                            except Exception:
                                attrs = None
                    params["attributes"] = attrs

                if LOG_ROWS:
                    log.info("[%s] row %d params (sanitized): %r", revision, idx, {k:v for k,v in params.items() if k in param_keys})

                try:
                    with _per_row_tx(bind):
                        bind.execute(insert_stmt, params)
                        inserted += 1
                        if VERIFY_EVERY:
                            cnt = bind.execute(sa.text(f"SELECT COUNT(*) FROM {ORDERS_TBL}")).scalar()
                            log.info("[%s] row %d count=%s", revision, idx, cnt)
                except Exception:
                    skipped += 1
                    log.exception("[%s] row %d failed to insert; params=%r", revision, idx, params)

    finally:
        try:
            fobj.close()
        except Exception:
            pass

    log.info("[%s] CSV rows=%d, inserted=%d, skipped=%d", revision, total, inserted, skipped)
    if ABORT_IF_ZERO and inserted == 0:
        raise RuntimeError(f"[{revision}] No rows inserted; enable WO_LOG_ROWS=1 for per-row details.")

def downgrade() -> None:
    # Best-effort: delete orders that match CSV by (summary, description) if possible.
    bind = op.get_bind()
    csv_path = _find_csv(CSV_NAME)
    if not csv_path:
        log.info("[%s] downgrade: CSV not found; nothing to do.", revision)
        return
    reader, fobj = _open_csv(csv_path)
    try:
        keys = [(r.get("summary"), r.get("maintenance_description")) for r in reader]
    finally:
        try: fobj.close()
        except Exception: pass

    bind.execute(sa.text(f"DELETE FROM {ORDERS_TBL} WHERE summary = ANY(:summaries)"),
                 {"summaries": [k[0] for k in keys if k[0]]})
    log.info("[%s] downgrade: deleted by summary match (best-effort).", revision)
