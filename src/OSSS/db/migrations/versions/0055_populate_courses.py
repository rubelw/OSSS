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
revision = "0055_populate_courses"
down_revision = "0054_populate_pm_work_gen"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

COURSES_CSV_NAME = "courses.csv"

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
            continue
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

def _norm(s: str | None) -> str:
    return (s or "").strip().lower()

def _open_csv(csv_path: Path):
    f = csv_path.open("r", encoding="utf-8", newline="")
    return csv.DictReader(f), f

def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    # quick sanity: ensure target table exists
    existing = set(insp.get_table_names(schema=None))
    if "courses" not in existing:
        log.warning("[%s] table 'courses' missing — abort.", revision)
        return

    # resolve CSV
    csv_path = _find_csv(COURSES_CSV_NAME, envvar="COURSES_CSV_PATH")
    if not csv_path:
        raise RuntimeError(f"[{revision}] {COURSES_CSV_NAME} not found")

    # reflect needed cols
    course_cols = {c["name"] for c in insp.get_columns("courses")}
    has_id = "id" in course_cols
    has_subject_id = "subject_id" in course_cols
    has_school_id = "school_id" in course_cols
    has_name = "name" in course_cols
    has_code = "code" in course_cols
    has_credit_hours = "credit_hours" in course_cols
    has_created_at = "created_at" in course_cols
    has_updated_at = "updated_at" in course_cols

    # build lookup maps
    school_map = {}
    for r in bind.execute(sa.text("SELECT id, name FROM schools")).mappings():
        nm = _norm(r["name"])
        if nm and nm not in school_map:
            school_map[nm] = str(r["id"])

    subject_map = {}
    subj_cols = {c["name"] for c in insp.get_columns("subjects")}
    subj_name_col = "name" if "name" in subj_cols else ("title" if "title" in subj_cols else None)
    if subj_name_col is None:
        log.warning("[%s] subjects table has no 'name'/'title' column; subject lookups will be skipped.", revision)
    else:
        for r in bind.execute(sa.text(f"SELECT id, {subj_name_col} AS name FROM subjects")).mappings():
            nm = _norm(r["name"])
            if nm and nm not in subject_map:
                subject_map[nm] = str(r["id"])

    # prepare insert
    insert_cols = []
    insert_vals = []
    if has_id:
        insert_cols.append("id"); insert_vals.append("gen_random_uuid()")
    if has_school_id:
        insert_cols.append("school_id"); insert_vals.append(":school_id")
    if has_subject_id:
        insert_cols.append("subject_id"); insert_vals.append(":subject_id")
    if has_name:
        insert_cols.append("name"); insert_vals.append(":name")
    if has_code:
        insert_cols.append("code"); insert_vals.append(":code")
    if has_credit_hours:
        insert_cols.append("credit_hours"); insert_vals.append(":credit_hours")
    if has_created_at:
        insert_cols.append("created_at"); insert_vals.append("now()")
    if has_updated_at:
        insert_cols.append("updated_at"); insert_vals.append("now()")

    ins_sql = f"INSERT INTO courses ({', '.join(insert_cols)}) VALUES ({', '.join(insert_vals)})"
    ins = sa.text(ins_sql)
    if has_credit_hours:
        ins = ins.bindparams(sa.bindparam("credit_hours", type_=pg.NUMERIC(4,2)))

    # de-dupe check: (school_id, name) is a reasonable uniqueness proxy
    chk_sql = sa.text("SELECT 1 FROM courses WHERE school_id=:sid AND name=:nm LIMIT 1")

    # process CSV
    reader, fh = _open_csv(csv_path)
    inserted = skipped = missing_map = 0
    try:
        for idx, raw in enumerate(reader, start=1):
            school_name = _norm(raw.get("school_name"))
            subject_name = _norm(raw.get("subject_name"))
            course_name = raw.get("name")
            course_code = raw.get("code")
            credit_hours = raw.get("credit_hours")

            sid = school_map.get(school_name)
            if not sid:
                log.warning("[%s] row %d: unknown school %r — skipping", revision, idx, school_name)
                missing_map += 1
                continue

            subid = None
            if has_subject_id and subject_name:
                subid = subject_map.get(subject_name)
                if subject_name and not subid:
                    log.info("[%s] row %d: subject %r not found — inserting with NULL subject_id", revision, idx, subject_name)

            # de-dupe
            if bind.execute(chk_sql, {"sid": sid, "nm": course_name}).scalar():
                skipped += 1
                continue

            params = {
                "school_id": sid,
                "subject_id": subid,
                "name": course_name,
                "code": course_code,
            }
            if has_credit_hours:
                try:
                    params["credit_hours"] = None if credit_hours in (None, "",) else float(credit_hours)
                except Exception:
                    params["credit_hours"] = None

            bind.execute(ins, params)
            inserted += 1

    finally:
        try:
            fh.close()
        except Exception:
            pass

    log.info("[%s] populate courses complete: inserted=%s skipped=%s missing_map=%s from_csv=%s",
             revision, inserted, skipped, missing_map, csv_path)

    if inserted == 0:
        # surface a helpful error to make debugging easier
        raise RuntimeError(f"[{revision}] No rows inserted from {csv_path}. "
                           f"Check that school/subject names in CSV match existing rows in schools/subjects.")

def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "courses" not in set(insp.get_table_names(schema=None)):
        log.info("[%s] downgrade: 'courses' table missing; nothing to do.", revision)
        return

    csv_path = _find_csv(COURSES_CSV_NAME)
    if not csv_path:
        log.warning("[%s] downgrade: %s not found; skipping deletion.", revision, COURSES_CSV_NAME)
        return

    def _norm(s: str | None) -> str:
        return (s or "").strip().lower()

    # Build school name -> id (again)
    school_map = {}
    for r in bind.execute(sa.text("SELECT id, name FROM schools")).mappings():
        nm = _norm(r["name"])
        if nm and nm not in school_map:
            school_map[nm] = str(r["id"])

    # Delete rows that were created by this CSV (match on school_id and course name)
    reader = csv.DictReader(csv_path.open("r", encoding="utf-8", newline=""))
    names_by_school = {}
    for raw in reader:
        sname = _norm(raw.get("school_name"))
        cname = raw.get("name")
        sid = school_map.get(sname)
        if sid and cname:
            names_by_school.setdefault(sid, set()).add(cname)

    total_deleted = 0
    for sid, names in names_by_school.items():
        q = sa.text("DELETE FROM courses WHERE school_id=:sid AND name = ANY(:names)")
        q = q.bindparams(sa.bindparam("names", type_=pg.ARRAY(pg.TEXT)))
        res = bind.execute(q, {"sid": sid, "names": list(names)})
        total_deleted += getattr(res, "rowcount", 0) or 0

    log.info("[%s] downgrade: deleted %s rows from courses matching CSV.", revision, total_deleted)
