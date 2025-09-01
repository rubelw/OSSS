"""Populate pm_work_generators from CSV (robust plan lookup + **extra debug logging** + plan_name→plan_id + deep diagnostics)."""

from __future__ import annotations

import os, csv, logging, re, json
from pathlib import Path
from datetime import datetime
from contextlib import nullcontext

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

# ---- Alembic identifiers ----
revision = "0056_populate_course_sec"
down_revision = "0055_populate_courses"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")


# ---- Verbosity toggles (env-driven) ----
LOG_LVL = os.getenv("CS_LOG_LEVEL", "INFO").upper()
LOG_ROWS = os.getenv("CS_LOG_ROWS", "0") == "1"            # log every row at INFO
ABORT_IF_ZERO = os.getenv("CS_ABORT_IF_ZERO", "0") == "1"  # raise if nothing inserted

logging.getLogger("alembic.runtime.migration").setLevel(getattr(logging, LOG_LVL, logging.INFO))
logging.getLogger("sqlalchemy.engine").setLevel(getattr(logging, LOG_LVL, logging.INFO))

COURSES_TBL = "courses"
TERMS_TBL   = "academic_terms"
SECTS_TBL   = "course_sections"
SCHOOLS_TBL = "schools"

CSV_NAME = "course_sections.csv"  # default filename
CSV_ENV  = "COURSE_SECTIONS_CSV_PATH"  # optional override

# ---- small utils ------------------------------------------------------------

def _norm(s: str | None) -> str:
    return (s or "").replace("\ufeff", "").strip().lower()

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
    # Keep it simple: standard CSV with header row
    f = csv_path.open("r", encoding="utf-8", newline="")
    return csv.DictReader(f), f

def _table_count(bind, table: str) -> int:
    try:
        return int(bind.execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar() or 0)
    except Exception:
        log.exception("[%s] failed to count rows for table %s", revision, table)
        return -1

def _uuid_sql(bind) -> str:
    # choose gen_random_uuid() or uuid_generate_v4()
    for name in ("gen_random_uuid", "uuid_generate_v4"):
        try:
            if bind.execute(sa.text("SELECT 1 FROM pg_proc WHERE proname=:n"), {"n": name}).scalar():
                log.info("[%s] using %s()", revision, name)
                return f"{name}()"
        except Exception:
            pass
    log.warning("[%s] no native UUID helper found; defaulting to gen_random_uuid()", revision)
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

def _per_row_tx(conn):
    try:
        return conn.begin_nested()
    except Exception:
        return nullcontext()

# ---- migration --------------------------------------------------------------

def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    # Sanity: tables present?
    existing = set(insp.get_table_names(schema=None))
    for t in (COURSES_TBL, TERMS_TBL, SECTS_TBL):
        if t not in existing:
            log.error("[%s] required table %r is missing; aborting.", revision, t)
            return

    pre_sects = _table_count(bind, SECTS_TBL)
    log.info("[%s] pre-state count: %s=%s", revision, SECTS_TBL, pre_sects)

    # CSV path
    csv_path = _find_csv(CSV_NAME, CSV_ENV)
    if not csv_path:
        raise RuntimeError(f"[{revision}] {CSV_NAME} not found (set {CSV_ENV} to override).")

    # Preview header
    try:
        with open(csv_path, "r", encoding="utf-8") as fh:
            head = [next(fh).rstrip("\n") for _ in range(5)]
        log.info("[%s] %s head:\n    %s", revision, getattr(csv_path, "name", str(csv_path)), "\n    ".join(head))
    except Exception:
        log.exception("[%s] failed to preview CSV head", revision)

    # Build lookup maps
    # Courses: name -> (id, school_id)
    course_rows = bind.execute(sa.text(f"SELECT id, name, school_id FROM {COURSES_TBL}")).mappings().all()
    course_by_name = {}
    course_school = {}
    for r in course_rows:
        nm = _norm(r["name"])
        cid = str(r["id"])
        course_by_name.setdefault(nm, cid)
        course_school[cid] = str(r["school_id"]) if r["school_id"] is not None else None
    log.info("[%s] loaded courses: %d (unique names=%d)", revision, len(course_rows), len(course_by_name))

    # Terms: name -> id
    term_rows = bind.execute(sa.text(f"SELECT id, name FROM {TERMS_TBL}")).mappings().all()
    term_by_name = { _norm(r["name"]): str(r["id"]) for r in term_rows }
    log.info("[%s] loaded terms: %d (unique names=%d)", revision, len(term_rows), len(term_by_name))

    # Column presence
    sect_cols = {c["name"] for c in insp.get_columns(SECTS_TBL)}
    has_capacity = "capacity" in sect_cols
    has_created_at = "created_at" in sect_cols
    has_updated_at = "updated_at" in sect_cols

    # Queries
    uuid_sql = _uuid_sql(bind)
    ins_cols = ["id", "course_id", "term_id", "section_number", "school_id"]
    ins_vals = [uuid_sql, ":course_id", ":term_id", ":section_number", ":school_id"]
    if has_capacity:
        ins_cols.append("capacity"); ins_vals.append(":capacity")
    if has_created_at:
        ins_cols.append("created_at"); ins_vals.append("now()")
    if has_updated_at:
        ins_cols.append("updated_at"); ins_vals.append("now()")

    ins_sql = f"INSERT INTO {SECTS_TBL} ({', '.join(ins_cols)}) VALUES ({', '.join(ins_vals)}) RETURNING id"
    ins = sa.text(ins_sql)
    ins = ins.bindparams(
        sa.bindparam("course_id"),
        sa.bindparam("term_id"),
        sa.bindparam("section_number"),
        sa.bindparam("school_id"),
    )
    if has_capacity:
        ins = ins.bindparams(sa.bindparam("capacity", type_=sa.Integer))

    exists_sql = sa.text(
        f"SELECT 1 FROM {SECTS_TBL} WHERE course_id=:course_id AND term_id=:term_id AND section_number=:section_number LIMIT 1"
    )

    # Iterate CSV
    inserted = 0
    skipped = 0
    missing = 0
    total = 0

    reader, fobj = _open_csv(csv_path)
    try:
        log.info("[%s] CSV header: %s", revision, reader.fieldnames)

        with _outer_tx(bind):
            for i, raw in enumerate(reader, start=1):
                total += 1
                course_name = _norm(raw.get("course_name"))
                term_name   = _norm(raw.get("term_name"))
                section_number = (raw.get("section_number") or "001").strip()
                capacity_val = raw.get("capacity")
                capacity = None
                if capacity_val not in (None, "", "NULL", "null"):
                    try:
                        capacity = int(capacity_val)
                    except Exception:
                        capacity = None

                if LOG_ROWS:
                    log.info("[%s] row %d raw=%r", revision, i, raw)

                course_id = course_by_name.get(course_name)
                term_id   = term_by_name.get(term_name)
                if not course_id or not term_id:
                    log.warning("[%s] row %d missing ids course_id=%s term_id=%s (course_name=%r term_name=%r)",
                                revision, i, course_id, term_id, course_name, term_name)
                    missing += 1
                    continue

                school_id = course_school.get(course_id)
                if not school_id:
                    # fallback: join at runtime
                    try:
                        school_id = bind.execute(sa.text(f"SELECT school_id FROM {COURSES_TBL} WHERE id=:cid"), {"cid": course_id}).scalar()
                    except Exception:
                        school_id = None

                # idempotency
                if bind.execute(exists_sql, {
                    "course_id": course_id, "term_id": term_id, "section_number": section_number
                }).scalar():
                    skipped += 1
                    if LOG_ROWS:
                        log.info("[%s] row %d exists: (%s, %s, %s)", revision, i, course_id, term_id, section_number)
                    continue

                params = {
                    "course_id": course_id,
                    "term_id": term_id,
                    "section_number": section_number,
                    "school_id": school_id,
                }
                if has_capacity:
                    params["capacity"] = capacity

                try:
                    with _per_row_tx(bind):
                        res = bind.execute(ins, params).scalar()
                        inserted += 1
                        if LOG_ROWS:
                            log.info("[%s] row %d inserted id=%s course=%s term=%s section=%s capacity=%s school=%s",
                                     revision, i, res, course_id, term_id, section_number, capacity, school_id)
                except Exception:
                    log.exception("[%s] row %d failed to insert; params=%r", revision, i, params)

    finally:
        try:
            fobj.close()
        except Exception:
            pass

    post_sects = _table_count(bind, SECTS_TBL)
    delta = (post_sects if isinstance(post_sects, int) else 0) - (pre_sects if isinstance(pre_sects, int) else 0)
    log.info("[%s] summary: rows_in_csv=%d inserted=%d skipped=%d missing=%d — %s pre=%s post=%s delta=%s",
             revision, total, inserted, skipped, missing, SECTS_TBL, pre_sects, post_sects, delta)

    if ABORT_IF_ZERO and inserted == 0:
        raise RuntimeError(f"[{revision}] No rows inserted; inspect logs with CS_LOG_ROWS=1")

def downgrade() -> None:
    bind = op.get_bind()

    csv_path = _find_csv(CSV_NAME, CSV_ENV)
    if not csv_path:
        log.warning("[%s] downgrade: %s not found; skipping deletion.", revision, CSV_NAME)
        return

    # Build name->id maps for deletion
    course_rows = bind.execute(sa.text(f"SELECT id, name FROM {COURSES_TBL}")).mappings().all()
    course_by_name = { _norm(r["name"]): str(r["id"]) for r in course_rows }

    term_rows = bind.execute(sa.text(f"SELECT id, name FROM {TERMS_TBL}")).mappings().all()
    term_by_name = { _norm(r["name"]): str(r["id"]) for r in term_rows }

    reader, fobj = _open_csv(csv_path)
    try:
        combos = []
        for raw in reader:
            course_name = _norm(raw.get("course_name"))
            term_name   = _norm(raw.get("term_name"))
            section_number = (raw.get("section_number") or "001").strip()
            cid = course_by_name.get(course_name)
            tid = term_by_name.get(term_name)
            if cid and tid:
                combos.append((cid, tid, section_number))

        if not combos:
            log.info("[%s] downgrade: no matching combos found; nothing to delete.", revision)
            return

        del_sql = sa.text(
            f"DELETE FROM {SECTS_TBL} WHERE (course_id, term_id, section_number) IN :combos"
        )
        # SQLAlchemy requires using tuple_ for IN of tuples; do it in Python string form
        tuples_literal = ", ".join([f"('{c}', '{t}', '{s}')" for c, t, s in combos])
        stmt = sa.text(f"DELETE FROM {SECTS_TBL} WHERE (course_id, term_id, section_number) IN ({tuples_literal})")

        with _outer_tx(bind):
            result = bind.execute(stmt)
            rc = getattr(result, "rowcount", None)
            log.info("[%s] downgrade: delete completed; rowcount=%s", revision, rc)

    finally:
        try:
            fobj.close()
        except Exception:
            pass