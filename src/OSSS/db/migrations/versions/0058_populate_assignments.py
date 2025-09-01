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
revision = "0058_populate_assignments"
down_revision = "0057_populate_assignment_cat"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")
LOG_LVL = os.getenv("ASSIGN_LOG_LEVEL", "INFO").upper()
LOG_ROWS = os.getenv("ASSIGN_LOG_ROWS", "0") == "1"
TRACE = os.getenv("ASSIGN_TRACE_LOOKUPS", "0") == "1"
ABORT_IF_ZERO = os.getenv("ASSIGN_ABORT_IF_ZERO", "0") == "1"

logging.getLogger("alembic.runtime.migration").setLevel(getattr(logging, LOG_LVL, logging.INFO))
logging.getLogger("sqlalchemy.engine").setLevel(getattr(logging, LOG_LVL, logging.INFO))

ASSIGN_CSV = os.getenv("ASSIGNMENTS_CSV_PATH", "")
ASSIGN_CSV_DEFAULT = "assignments.csv"

ASSIGN_TBL   = "assignments"
SECTIONS_TBL = "course_sections"
COURSES_TBL  = "courses"
TERMS_TBL    = "academic_terms"
CATS_TBL     = "assignment_categories"

def _find_csv() -> Path | None:
    here = Path(__file__).resolve()
    candidates = [
        Path(ASSIGN_CSV) if ASSIGN_CSV else None,
        here.with_name(ASSIGN_CSV_DEFAULT),
        here.parent / "data" / ASSIGN_CSV_DEFAULT,
        here.parent.parent / "data" / ASSIGN_CSV_DEFAULT,
        Path.cwd() / ASSIGN_CSV_DEFAULT,
        Path("/mnt/data") / ASSIGN_CSV_DEFAULT,
    ]
    for p in candidates:
        if p and p.exists():
            log.info("[%s] using CSV: %s", revision, p)
            return p
    log.warning("[%s] %s not found in standard locations", revision, ASSIGN_CSV_DEFAULT)
    return None

def _norm(s: str | None) -> str:
    return (s or "").strip()

def _lower(s: str | None) -> str:
    return _norm(s).lower()

def _to_decimal(s: str | None):
    if s is None or _norm(s) == "":
        return None
    try:
        return Decimal(_norm(s))
    except InvalidOperation:
        return None

def _parse_date(s: str | None):
    if not s:
        return None
    v = _norm(s)
    if not v:
        return None
    try:
        # try ISO first
        return date.fromisoformat(v)
    except Exception:
        # best-effort: mm/dd/yyyy
        try:
            m, d, y = v.split("/")
            return date(int(y), int(m), int(d))
        except Exception:
            return None

def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)

    # sanity: tables present
    needed = {ASSIGN_TBL, SECTIONS_TBL, COURSES_TBL, TERMS_TBL}
    existing = set(insp.get_table_names(schema=None))
    missing = needed - existing
    if missing:
        log.warning("[%s] missing tables: %s — aborting", revision, sorted(missing))
        return

    # load section composite index: (course_lower, term_lower, section_number variants) -> section_id
    # join to get names in one query
    sec_index = {}
    rows = bind.execute(sa.text(f"""
        SELECT cs.id, c.name AS course_name, t.name AS term_name, cs.section_number
        FROM {SECTIONS_TBL} cs
        JOIN {COURSES_TBL}  c ON c.id = cs.course_id
        JOIN {TERMS_TBL}    t ON t.id = cs.term_id
    """)).mappings().all()

    def variants(secno: str):
        s = _norm(secno)
        if not s:
            return []
        v = {s}
        # numeric paddings if numeric
        if s.isdigit():
            v.add(s.zfill(2))
            v.add(s.zfill(3))
        return list(v)

    for r in rows:
        cid = str(r["id"])
        c = _lower(r["course_name"])
        t = _lower(r["term_name"])
        for sn in variants(r["section_number"]):
            sec_index[(c, t, sn)] = cid

    log.info("[%s] section index built: %d keys for %d sections",
             revision, len(sec_index), len({r['id'] for r in rows}))

    # optional: categories per section
    cat_index = {}
    if CATS_TBL in existing:
        cat_rows = bind.execute(sa.text(f"SELECT id, section_id, name FROM {CATS_TBL}")).mappings().all()
        for cr in cat_rows:
            cat_index[(str(cr["section_id"]), _lower(cr["name"]))] = str(cr["id"])
        log.info("[%s] category index built: %d keys", revision, len(cat_index))

    # CSV
    csv_path = _find_csv()
    if not csv_path:
        raise RuntimeError(f"[{revision}] assignments.csv not found")

    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        hdr = [h for h in (reader.fieldnames or [])]
        log.info("[%s] CSV header: %s", revision, hdr)

        def pick(row, *names):
            for n in names:
                if n in row and row[n] not in (None, "", "NULL", "null"):
                    return str(row[n]).strip()
            return ""

        # prepare insert
        cols = {c["name"] for c in insp.get_columns(ASSIGN_TBL)}
        has_cat = "category_id" in cols
        ins_cols = ["id", "section_id", "name"]
        vals = ["gen_random_uuid()", ":section_id", ":name"]
        if has_cat:
            ins_cols.append("category_id"); vals.append(":category_id")
        if "due_date" in cols:
            ins_cols.append("due_date"); vals.append(":due_date")
        if "points_possible" in cols:
            ins_cols.append("points_possible"); vals.append(":points_possible")
        if "created_at" in cols:
            ins_cols.append("created_at"); vals.append("now()")
        if "updated_at" in cols:
            ins_cols.append("updated_at"); vals.append("now()")

        ins = sa.text(f"INSERT INTO {ASSIGN_TBL} ({', '.join(ins_cols)}) VALUES ({', '.join(vals)})")
        if has_cat:
            ins = ins.bindparams(sa.bindparam("category_id"))
        if "due_date" in cols:
            ins = ins.bindparams(sa.bindparam("due_date", type_=sa.Date()))
        if "points_possible" in cols:
            ins = ins.bindparams(sa.bindparam("points_possible", type_=pg.NUMERIC(8,2)))
        ins = ins.bindparams(sa.bindparam("section_id"), sa.bindparam("name"))

        # idempotence check (section_id + name)
        chk = sa.text(f"SELECT 1 FROM {ASSIGN_TBL} WHERE section_id=:sid AND name=:nm LIMIT 1")

        inserted = skipped = missing = existed = 0
        for i, raw in enumerate(reader, start=1):
            course = pick(raw, "course_name","course")
            term   = pick(raw, "term_name","term")
            secno  = pick(raw, "section_number","section","sec","number")
            name   = pick(raw, "name","title")
            catnm  = pick(raw, "category_name","category")
            due    = pick(raw, "due_date","due")

            # REQUIRED: lookup by (course_lower, term_lower, section_number) — section_number is authoritative
            sid = None
            key_variants = [( _lower(course), _lower(term), secno ),
                            ( _lower(course), _lower(term), secno.zfill(2) if secno.isdigit() else secno ),
                            ( _lower(course), _lower(term), secno.zfill(3) if secno.isdigit() else secno )]
            for k in key_variants:
                sid = sec_index.get(k)
                if sid:
                    break

            if not sid:
                missing += 1
                if TRACE or LOG_ROWS:
                    log.warning("[%s] row %d no section_id for (course=%r, term=%r, section_number=%r) — skipping",
                                revision, i, course, term, secno)
                continue

            # category (optional)
            cat_id = None
            if catnm:
                cat_id = cat_index.get((sid, _lower(catnm)))

            params = {
                "section_id": sid,
                "name": name or f"Assignment {i}",
            }
            if "due_date" in cols:
                d = _parse_date(due)
                params["due_date"] = d
            if "points_possible" in cols:
                try_pts = pick(raw, "points_possible","points")
                from decimal import Decimal
                params["points_possible"] = Decimal(try_pts) if try_pts else None

            if has_cat:
                params["category_id"] = cat_id

            # idempotence
            if bind.execute(chk, {"sid": sid, "nm": params["name"]}).scalar():
                existed += 1
                if LOG_ROWS:
                    log.info("[%s] row %d exists: section_id=%s name=%r", revision, i, sid, params["name"])
                continue

            try:
                bind.execute(ins, params)
                inserted += 1
                if LOG_ROWS:
                    log.info("[%s] row %d inserted: %r", revision, i, params)
            except Exception:
                skipped += 1
                log.exception("[%s] row %d failed insert: %r", revision, i, params)

        log.info("[%s] summary: inserted=%d, existed=%d, missing_section=%d, skipped=%d",
                 revision, inserted, existed, missing, skipped)

        if ABORT_IF_ZERO and inserted == 0:
            raise RuntimeError(f"[{revision}] No rows inserted")

def downgrade():
    # no-op (data-only migration)
    pass
