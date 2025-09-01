"""Populate work_order_parts from CSV (flex headers + robust parsing + FK preflight + loud logging)."""

from __future__ import annotations
import os, csv, logging, re
from pathlib import Path
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from contextlib import nullcontext
from itertools import cycle

from alembic import op
import sqlalchemy as sa

# ---- Alembic identifiers ----
revision = "0064_populate_wo_parts"
down_revision = "0064_populate_wo_tasks"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")


# ---- Env toggles -------------------------------------------------------------
LOG_LVL        = os.getenv("WOP_LOG_LEVEL", "DEBUG").upper()
LOG_SQL        = os.getenv("WOP_LOG_SQL", "0") == "1"
LOG_ROWS       = os.getenv("WOP_LOG_ROWS", "1") == "1"   # default ON to diagnose
ABORT_IF_ZERO  = os.getenv("WOP_ABORT_IF_ZERO", "1") == "1"
CSV_ENV        = "WORK_ORDER_PARTS_CSV_PATH"
CSV_NAME       = "work_order_parts.csv"
WOP_ROWS       = int(os.getenv("WOP_ROWS", "200"))  # rows to auto-generate if CSV absent

# allow fallback lookups if CSV doesn't have UUIDs
ALLOW_NAME_LOOKUPS  = os.getenv("WOP_ALLOW_NAME_LOOKUPS", "1") == "1"

logging.getLogger("alembic.runtime.migration").setLevel(getattr(logging, LOG_LVL, logging.INFO))
engine_logger = logging.getLogger("sqlalchemy.engine")
engine_logger.setLevel(logging.INFO if LOG_SQL else getattr(logging, LOG_LVL, logging.INFO))

# ---- Tables ------------------------------------------------------------------
ORDERS_TBL = "work_orders"
PARTS_TBL  = "parts"
WOP_TBL    = "work_order_parts"

# ---- Helpers -----------------------------------------------------------------
_norm_ws_re = re.compile(r"\s+")
_uuid_re = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$", re.I)

def _looks_uuid(s: str | None) -> bool:
    return bool(s and _uuid_re.match(str(s).strip()))

def _none_if_blank(v):
    if v is None: return None
    if isinstance(v, str) and v.strip() == "": return None
    return v

def _dec(v):
    v = _none_if_blank(v)
    if v is None: return None
    s = str(v).strip().replace(",", "")
    if s.startswith("$"): s = s[1:]
    try:
        q = Decimal(s)
    except (InvalidOperation, ValueError):
        return None
    return q.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

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

def _candidate_paths(name: str) -> list[Path]:
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
    # fall back to co-located with this migration
    return Path(__file__).resolve().with_name(name)

def _generate_csv(bind, insp) -> Path:
    """Create CSV deterministically by zipping work_orders with parts."""
    out = _default_output_path(CSV_NAME)
    out.parent.mkdir(parents=True, exist_ok=True)

    # detect parts.unit_cost presence
    pcols = {c["name"] for c in insp.get_columns(PARTS_TBL)}
    have_unit = "unit_cost" in pcols

    # fetch candidates
    wo_sql = sa.text(f"SELECT id FROM {ORDERS_TBL} ORDER BY created_at NULLS LAST, id")
    pt_sql = sa.text(f"SELECT id{', unit_cost' if have_unit else ''} FROM {PARTS_TBL} ORDER BY name NULLS LAST, id")

    wo_ids = [str(r[0]) for r in bind.execute(wo_sql).fetchall()]
    parts  = [{"id": str(r[0]), "unit_cost": (r[1] if have_unit else None)} for r in bind.execute(pt_sql).fetchall()]

    if not wo_ids:
        raise RuntimeError(f"[{revision}] cannot auto-generate CSV: no rows in {ORDERS_TBL}")
    if not parts:
        raise RuntimeError(f"[{revision}] cannot auto-generate CSV: no rows in {PARTS_TBL}")

    # deterministic “zip & cycle” generation
    count = min(WOP_ROWS, len(wo_ids))
    cy_parts = cycle(parts)

    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["work_order_id","part_id","qty","unit_cost","extended_cost","notes"])
        for i in range(count):
            wid = wo_ids[i]
            part = next(cy_parts)
            pid = part["id"]
            unit = _dec(part["unit_cost"]) or Decimal("10.00")
            qty  = Decimal("1.00")
            ext  = (qty * unit).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            w.writerow([wid, pid, f"{qty:.2f}", f"{unit:.2f}", f"{ext:.2f}", ""])

    log.info("[%s] generated %s rows into %s", revision, count, out)
    return out

def _ensure_csv(bind, insp) -> Path:
    path = _locate_existing_csv(CSV_NAME)
    if path:
        return path
    log.warning("[%s] %s not found — auto-generating from DB …", revision, CSV_NAME)
    return _generate_csv(bind, insp)

def _canon(k: str) -> str:
    k = k.strip().lower().replace("-", "_")
    k = _norm_ws_re.sub("_", k)
    return k

ALIASES = {
    "work_order_id": {"work_order_id","workorder_id","work_order","wo_id","workorder","work_order_uuid"},
    "work_order_summary": {"work_order_summary","wo_summary","summary"},
    "part_id": {"part_id","partid","parts_id","part","part_uuid"},
    "part_code": {"part_code","code","sku"},
    "part_name": {"part_name","name","item_name"},
    "qty": {"qty","quantity","qnty","amount"},
    "unit_cost": {"unit_cost","unitcost","price","unitprice"},
    "extended_cost": {"extended_cost","extendedcost","total","total_cost","ext_cost"},
    "notes": {"notes","note","comment","comments"},
}

def _flex_get(row: dict, key: str):
    # direct match
    if key in row and row[key] not in (None, ""):
        return row[key]
    for alt in ALIASES.get(key, {key}):
        for k in row.keys():
            if _canon(k) == _canon(alt):
                v = row.get(k)
                if v not in (None, ""):
                    return v
    return None

# ---- Insert builder ----------------------------------------------------------
def _insert_sql(bind):
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns(WOP_TBL)}
    ins_cols, vals = ["id"], ["gen_random_uuid()"]

    def add(col):
        if col in cols:
            ins_cols.append(col)
            vals.append(f":{col}")

    for c in ("work_order_id","part_id","qty","unit_cost","extended_cost","notes"):
        add(c)
    if "created_at" in cols: ins_cols.append("created_at"); vals.append("now()")
    if "updated_at" in cols: ins_cols.append("updated_at"); vals.append("now()")
    sql = sa.text(f"INSERT INTO {WOP_TBL} ({', '.join(ins_cols)}) VALUES ({', '.join(vals)})")
    return sql

# ---- Lookup caches -----------------------------------------------------------
def _build_caches(bind):
    insp = sa.inspect(bind)

    # Work orders
    wo_ids = {str(r[0]) for r in bind.execute(sa.text(f"SELECT id FROM {ORDERS_TBL}")).fetchall()}
    log.info("[%s] work_orders in DB: %d", revision, len(wo_ids))

    # Optional summary lookup
    has_summary = any(c["name"] == "summary" for c in insp.get_columns(ORDERS_TBL))
    wo_by_summary = {}
    if has_summary:
        rows = bind.execute(sa.text(f"SELECT id, summary FROM {ORDERS_TBL} WHERE summary IS NOT NULL")).mappings().all()
        for r in rows:
            s = r["summary"].strip().lower()
            wo_by_summary.setdefault(s, str(r["id"]))
        log.info("[%s] work_order summary index: %d", revision, len(wo_by_summary))

    # Parts
    part_ids = {str(r[0]) for r in bind.execute(sa.text(f"SELECT id FROM {PARTS_TBL}")).fetchall()}
    log.info("[%s] parts in DB: %d", revision, len(part_ids))

    # Optional code / name lookups
    cols = {c["name"] for c in insp.get_columns(PARTS_TBL)}
    part_by_code, part_by_name = {}, {}
    if "code" in cols:
        rows = bind.execute(sa.text(f"SELECT id, code FROM {PARTS_TBL} WHERE code IS NOT NULL")).mappings().all()
        for r in rows:
            part_by_code[r["code"].strip().lower()] = str(r["id"])
        log.info("[%s] parts code index: %d", revision, len(part_by_code))
    if "name" in cols:
        rows = bind.execute(sa.text(f"SELECT id, name FROM {PARTS_TBL} WHERE name IS NOT NULL")).mappings().all()
        for r in rows:
            part_by_name[r["name"].strip().lower()] = str(r["id"])
        log.info("[%s] parts name index: %d", revision, len(part_by_name))

    return wo_ids, wo_by_summary, part_ids, part_by_code, part_by_name

# ---- Migration ---------------------------------------------------------------
def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    # Ensure CSV exists (generate if missing)
    csv_path = _ensure_csv(bind, insp)
    reader, fobj = _open_csv(csv_path)

    wo_ids, wo_by_summary, part_ids, part_by_code, part_by_name = _build_caches(bind)
    insert_stmt = _insert_sql(bind)

    total = inserted = skipped = 0
    missing_wo = missing_pt = 0

    try:
        with _outer_tx(bind):
            for idx, raw in enumerate(reader, start=1):
                total += 1
                row = { (k if not isinstance(k, str) else k.strip()): (v.strip() if isinstance(v, str) else v)
                        for k, v in (raw or {}).items() }

                # ---- resolve work_order_id ----
                wo_val = _flex_get(row, "work_order_id")
                wo_id = None
                if wo_val and _looks_uuid(wo_val) and str(wo_val) in wo_ids:
                    wo_id = str(wo_val)
                elif ALLOW_NAME_LOOKUPS:
                    # try by summary
                    wos = _flex_get(row, "work_order_summary")
                    if wos:
                        wo_id = wo_by_summary.get(wos.strip().lower())

                if not wo_id:
                    missing_wo += 1
                    skipped += 1
                    if LOG_ROWS:
                        log.warning("[%s] row %d: cannot resolve work_order (got id=%r, summary=%r) — skipping",
                                    revision, idx, wo_val, _flex_get(row, "work_order_summary"))
                    continue

                # ---- resolve part_id ----
                pt_val = _flex_get(row, "part_id")
                part_id = None
                if pt_val and _looks_uuid(pt_val) and str(pt_val) in part_ids:
                    part_id = str(pt_val)
                elif ALLOW_NAME_LOOKUPS:
                    pcode = _flex_get(row, "part_code")
                    pname = _flex_get(row, "part_name")
                    if pcode:
                        part_id = part_by_code.get(pcode.strip().lower())
                    if not part_id and pname:
                        part_id = part_by_name.get(pname.strip().lower())

                if not part_id:
                    missing_pt += 1
                    skipped += 1
                    if LOG_ROWS:
                        log.warning("[%s] row %d: cannot resolve part (got id=%r, code=%r, name=%r) — skipping",
                                    revision, idx, pt_val, _flex_get(row, "part_code"), _flex_get(row, "part_name"))
                    continue

                qty  = _dec(_flex_get(row, "qty")) or Decimal("1.00")
                unit = _dec(_flex_get(row, "unit_cost"))
                ext  = _dec(_flex_get(row, "extended_cost"))
                if ext is None and unit is not None:
                    ext = (qty * unit).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

                params = {
                    "work_order_id": wo_id,
                    "part_id": part_id,
                    "qty": qty,
                    "unit_cost": unit,
                    "extended_cost": ext,
                    "notes": (_flex_get(row, "notes") or None),
                }

                if LOG_ROWS:
                    dbg = {k: (str(v) if isinstance(v, Decimal) else v) for k, v in params.items()}
                    log.info("[%s] row %d -> %r", revision, idx, dbg)

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

    log.info("[%s] done: CSV rows=%d, inserted=%d, skipped=%d (missing_wo=%d, missing_pt=%d) [csv=%s]",
             revision, total, inserted, skipped, missing_wo, missing_pt, csv_path)

    if ABORT_IF_ZERO and inserted == 0:
        raise RuntimeError(f"[{revision}] No rows inserted. Enable WOP_LOG_LEVEL=DEBUG WOP_LOG_ROWS=1 and re-run to see per-row reasons.")

def downgrade() -> None:
    # No-op; keep data.
    pass
