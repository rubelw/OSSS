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
revision = "0057_populate_assignment_cat"
down_revision = "0056_populate_course_sec"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")


# ---- Verbosity toggles (env-driven) ----
LOG_LVL = os.getenv("ASSIGN_CAT_LOG_LEVEL", "INFO").upper()
LOG_ROWS = os.getenv("ASSIGN_CAT_LOG_ROWS", "0") == "1"           # log every row at INFO
LOG_INDEX = os.getenv("ASSIGN_CAT_LOG_INDEX", "0") == "1"         # dump many index keys
ABORT_IF_ZERO = os.getenv("ASSIGN_CAT_ABORT_IF_ZERO", "0") == "1"

logging.getLogger("alembic.runtime.migration").setLevel(getattr(logging, LOG_LVL, logging.INFO))
logging.getLogger("sqlalchemy.engine").setLevel(getattr(logging, LOG_LVL, logging.INFO))

# ---- Tables / CSV names ----
SECTIONS_TBL = "course_sections"
COURSES_TBL = "courses"
TERMS_TBL = "academic_terms"
DEST_TBL = "assignment_categories"

CSV_NAME = "assignment_categories.csv"  # columns: section_name, course_name, term_name, section_number, name, weight

# ---- helpers ----
_norm_ws_re = re.compile(r"\s+")
def _norm(s: str | None) -> str:
    if not s: return ""
    s = s.replace("\ufeff", "").strip().lower()
    return _norm_ws_re.sub(" ", s)

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

def _detect_section_name_col(insp) -> str | None:
    cols = {c["name"] for c in insp.get_columns(SECTIONS_TBL)}
    for cand in ("name", "section_name"):
        if cand in cols:
            return cand
    return None

def _choose_name_col(insp, table: str, preferred=("name","title","code")) -> str | None:
    cols = {c["name"] for c in insp.get_columns(table)}
    for c in preferred:
        if c in cols: return c
    # any text-like column as last resort
    for c in cols:
        if c not in ("id",): return c
    return None

def _build_section_index(bind, insp):
    """Return (name_index, composite_index).
    name_index: normalized section_name -> id (only if section table has name-like column).
    composite_index: (course_norm, term_norm, section_number_norm) -> id
    """
    name_col = _detect_section_name_col(insp)
    secnum_col = "section_number" if any(c["name"]=="section_number" for c in insp.get_columns(SECTIONS_TBL)) else None
    course_name_col = _choose_name_col(insp, COURSES_TBL)
    term_name_col = _choose_name_col(insp, TERMS_TBL)

    if not (secnum_col and course_name_col and term_name_col):
        log.warning("[%s] Lookup columns resolved -> section_number=%s course_name=%s term_name=%s", revision, secnum_col, course_name_col, term_name_col)

    select_cols = [f"cs.id", f"cs.{secnum_col}" if secnum_col else "NULL AS section_number"]
    if name_col:
        select_cols.append(f"cs.{name_col} AS cs_name")
    else:
        select_cols.append("NULL AS cs_name")
    select_cols.append(f"c.{course_name_col} AS course_name" if course_name_col else "NULL AS course_name")
    select_cols.append(f"t.{term_name_col} AS term_name" if term_name_col else "NULL AS term_name")

    q = sa.text(f"""
        SELECT {', '.join(select_cols)}
        FROM {SECTIONS_TBL} cs
        JOIN {COURSES_TBL} c ON c.id = cs.course_id
        JOIN {TERMS_TBL} t ON t.id = cs.term_id
    """)
    rows = bind.execute(q).mappings().all()

    name_index: dict[str, str] = {}
    composite_index: dict[tuple[str,str,str], str] = {}

    for r in rows:
        sid = str(r["id"])
        secname = _norm(r.get("cs_name"))
        course = _norm(r.get("course_name"))
        term = _norm(r.get("term_name"))
        secnum = _norm(r.get("section_number"))
        if secname:
            if secname not in name_index:
                name_index[secname] = sid
        if course or term or secnum:
            key = (course, term, secnum)
            if key not in composite_index:
                composite_index[key] = sid

    log.info("[%s] section index built: by_name=%d by_composite=%d", revision, len(name_index), len(composite_index))
    if LOG_INDEX:
        # Show a few examples
        log.info("[%s] name_index peek: %s", revision, list(name_index.items())[:10])
        log.info("[%s] composite_index peek: %s", revision, list(composite_index.items())[:10])
    return name_index, composite_index

# ---- migration ----
def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    # resolve CSV
    csv_path = _find_csv(CSV_NAME, envvar="ASSIGNMENT_CATEGORIES_CSV_PATH")
    if not csv_path:
        raise RuntimeError(f"[{revision}] {CSV_NAME} not found")

    # destination columns
    dest_cols = {c["name"] for c in insp.get_columns(DEST_TBL)}
    has_created = "created_at" in dest_cols
    has_updated = "updated_at" in dest_cols

    uuid_sql = _uuid_sql(bind)

    # build section indexes
    name_index, composite_index = _build_section_index(bind, insp)

    # prepare insert + existence check
    ins_cols = ["id", "section_id", "name"]
    ins_vals = [uuid_sql, ":section_id", ":name"]
    if "weight" in dest_cols:
        ins_cols.append("weight"); ins_vals.append(":weight")
    if has_created: ins_cols.append("created_at"); ins_vals.append("now()")
    if has_updated: ins_cols.append("updated_at"); ins_vals.append("now()")

    ins_sql = sa.text(f"INSERT INTO {DEST_TBL} ({', '.join(ins_cols)}) VALUES ({', '.join(ins_vals)})")
    chk_sql = sa.text(f"SELECT 1 FROM {DEST_TBL} WHERE section_id=:sid AND lower(name)=lower(:nm) LIMIT 1")

    inserted = skipped = 0
    total = 0

    with open(csv_path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        # normalize header keys
        headers = [h.strip().lower() for h in (reader.fieldnames or [])]
        lower_map = {h.lower(): h for h in (reader.fieldnames or [])}
        h_secname = lower_map.get("section_name") or lower_map.get("name")
        h_coursename = lower_map.get("course_name")
        h_termname = lower_map.get("term_name")
        h_secnum = lower_map.get("section_number")
        h_catname = lower_map.get("category_name") or lower_map.get("name")
        h_weight = lower_map.get("weight")

        if not h_catname:
            raise RuntimeError(f"[{revision}] CSV must include a 'name' (category name) column")

        for i, raw in enumerate(reader, start=1):
            total += 1
            cat_name = (raw.get(h_catname) or "").strip()
            weight_raw = (raw.get(h_weight) or "").strip() if h_weight else None
            section_id = None
            matched = None

            # 1) by section_name if present and we have index
            secname_val = (raw.get(h_secname) or "").strip().lower() if h_secname else ""
            if secname_val and secname_val in name_index:
                section_id = name_index[secname_val]
                matched = f"by_name:{secname_val}"

            # 2) by composite (course_name, term_name, section_number)
            if not section_id:
                course_val = (raw.get(h_coursename) or "").strip().lower()
                term_val = (raw.get(h_termname) or "").strip().lower()
                secnum_val = (raw.get(h_secnum) or "").strip().lower()
                key = (course_val, term_val, secnum_val)
                if key in composite_index:
                    section_id = composite_index[key]
                    matched = f"by_composite:{key}"

            if not section_id:
                log.warning("[%s] row %d: could not resolve section_id for csv=%r", revision, i, raw)
                skipped += 1
                continue

            # parse weight
            weight_val = None
            if weight_raw:
                try:
                    weight_val = Decimal(weight_raw)
                except InvalidOperation:
                    weight_val = None

            # idempotence: (section_id, name)
            if bind.execute(chk_sql, {"sid": section_id, "nm": cat_name}).scalar():
                if LOG_ROWS:
                    log.info("[%s] row %d: existed for section_id=%s name=%r (%s)", revision, i, section_id, cat_name, matched)
                continue

            with _per_row_tx(bind):
                params = {"section_id": section_id, "name": cat_name}
                if "weight" in dest_cols:
                    params["weight"] = weight_val
                bind.execute(ins_sql, params)
                if LOG_ROWS:
                    log.info("[%s] row %d: INSERTED section_id=%s name=%r weight=%r via %s", revision, i, section_id, cat_name, weight_val, matched)
                inserted += 1

    log.info("[%s] CSV rows=%d inserted=%d skipped=%d", revision, total, inserted, skipped)
    if ABORT_IF_ZERO and inserted == 0:
        raise RuntimeError(f"[{revision}] No rows inserted; set ASSIGN_CAT_LOG_ROWS=1 to debug")

def downgrade() -> None:
    bind = op.get_bind()
    csv_path = Path("/mnt/data") / CSV_NAME  # best effort
    if not csv_path.exists():
        log.warning("[%s] downgrade: %s not found; skipping delete.", revision, CSV_NAME)
        return
    # Read CSV and delete matching (section_id, name)
    with open(csv_path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        names = set()
        for row in reader:
            nm = (row.get("name") or row.get("category_name") or "").strip()
            if nm: names.add(nm.lower())
    if not names:
        log.info("[%s] downgrade: no names parsed; nothing to delete.", revision)
        return
    # Delete any assignment_categories with a name in set (broad but reversible)
    q = sa.text(f"DELETE FROM {DEST_TBL} WHERE lower(name) = ANY(:nms)").bindparams(sa.bindparam("nms", type_=pg.ARRAY(sa.Text())))
    res = bind.execute(q, {"nms": list(names)})
    rc = getattr(res, "rowcount", None)
    log.info("[%s] downgrade: deleted rowcount=%s", revision, rc)
