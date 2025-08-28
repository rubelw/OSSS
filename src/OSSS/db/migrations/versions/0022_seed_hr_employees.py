# versions/0022_seed_hr_employees.py
from __future__ import annotations

import os
import csv
import re
from pathlib import Path
from typing import Dict, List

from alembic import op
import sqlalchemy as sa

revision = "0022_seed_hr_employees"
down_revision = "0021_seed_persons"
branch_labels = None
depends_on = None


# ---- helpers ---------------------------------------------------------------
def _insp(conn):
    return sa.inspect(conn)

def _has_table(conn, table: str) -> bool:
    return table in _insp(conn).get_table_names()

def _has_column(conn, table: str, column: str) -> bool:
    return any(c["name"] == column for c in _insp(conn).get_columns(table))

def _has_fk(conn, table: str, name: str) -> bool:
    return any(fk["name"] == name for fk in _insp(conn).get_foreign_keys(table))

def _norm(s: str | None) -> str:
    return (s or "").strip()

def _slug(s: str | None) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s

def _read_seed_csv(csv_path: Path) -> List[Dict[str, str]]:
    """Read employees.csv with headers:
       first_name,middle_name,last_name,dob,email,phone,gender,unit
       Headers are treated case-insensitively; only names + unit are used here.
    """
    if not csv_path.exists():
        print(f"[seed hr_employees] CSV not found at: {csv_path} → skipping")
        return []
    with csv_path.open(newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        rows: List[Dict[str, str]] = []
        for row in r:
            d = { (k or "").strip().lower(): (v or "").strip() for k, v in row.items() }
            rows.append({
                "first_name":  _norm(d.get("first_name") or d.get("firstname")),
                "middle_name": _norm(d.get("middle_name") or d.get("middlename")),
                "last_name":   _norm(d.get("last_name")  or d.get("lastname")),
                "unit":        _slug(d.get("unit")),  # normalize to snake_case to match departments.name
            })
        return rows


# ---- migration -------------------------------------------------------------
def upgrade():
    conn = op.get_bind()

    # Ensure required tables exist
    for t in ("hr_employees", "departments", "persons"):
        if not _has_table(conn, t):
            print(f"[seed hr_employees] Table {t} does not exist → skipping.")
            return

    # Ensure employee_no sequence/default so NOT NULL doesn't block inserts
    op.execute("""
    DO $$
    BEGIN
      IF NOT EXISTS (
        SELECT 1 FROM pg_class WHERE relkind = 'S' AND relname = 'hr_employee_no_seq'
      ) THEN
        CREATE SEQUENCE hr_employee_no_seq START WITH 100000 INCREMENT BY 1 NO MINVALUE NO MAXVALUE CACHE 1;
      END IF;

      IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name   = 'hr_employees'
          AND column_name  = 'employee_no'
          AND column_default IS NOT NULL
      ) THEN
        ALTER TABLE hr_employees
          ALTER COLUMN employee_no
          SET DEFAULT ('E' || lpad(nextval('hr_employee_no_seq')::text, 7, '0'));
      END IF;
    END $$;
    """)

    # Ensure hr_employees columns/FKs (person_id, department_id)
    changed = False

    # person_id → persons(id)
    if not _has_column(conn, "hr_employees", "person_id"):
        op.add_column("hr_employees", sa.Column("person_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True))
        changed = True
    if not _has_fk(conn, "hr_employees", "fk_hr_employees_person_id"):
        op.create_foreign_key(
            "fk_hr_employees_person_id",
            "hr_employees", "persons",
            ["person_id"], ["id"],
            ondelete="SET NULL",
        )
        changed = True

    # department_id → departments(id)
    if not _has_column(conn, "hr_employees", "department_id"):
        op.add_column("hr_employees", sa.Column("department_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True))
        changed = True
    if not _has_fk(conn, "hr_employees", "fk_hr_employees_department_id"):
        op.create_foreign_key(
            "fk_hr_employees_department_id",
            "hr_employees", "departments",
            ["department_id"], ["id"],
            ondelete="SET NULL",
        )
        changed = True

    # Optionally also populate hr_employees.first_name/last_name if those columns exist
    has_fn = _has_column(conn, "hr_employees", "first_name")
    has_ln = _has_column(conn, "hr_employees", "last_name")

    if changed:
        print("[seed hr_employees] Added/verified columns & constraints.")

    # CSV path (employees.csv by request)
    script_dir = Path(__file__).resolve().parent
    default_csv = (script_dir / "employees.csv").resolve()
    csv_path = Path(os.environ.get("HR_EMPLOYEES_SEED_CSV", str(default_csv))).resolve()

    rows = _read_seed_csv(csv_path)
    # Need names + unit to place an employee (position no longer required)
    rows = [r for r in rows if r["first_name"] and r["last_name"] and r["unit"]]
    if not rows:
        print("[seed hr_employees] No seed rows → done.")
        return

    # Build VALUES with middle_name + unit
    vals, params = [], {}
    for i, r in enumerate(rows):
        vals.append(f"(:f{i}, :m{i}, :l{i}, :u{i})")
        params[f"f{i}"] = r["first_name"]
        params[f"m{i}"] = r["middle_name"] or None
        params[f"l{i}"] = r["last_name"]
        params[f"u{i}"] = r["unit"]              # already slugged
    values_sql = ", ".join(vals)

    # Insert by joining to persons (first + middle? + last) and departments(name=unit)
    # middle_name match is optional
    columns_to_insert = "person_id, department_id"
    select_name_cols = ""
    if has_fn and has_ln:
        columns_to_insert += ", first_name, last_name"
        select_name_cols = ", per.first_name, per.last_name"

    insert_sql = sa.text(f"""
        WITH s(first_name, middle_name, last_name, unit_slug) AS (
            VALUES {values_sql}
        ),
        per AS (
            SELECT p.id AS person_id, p.first_name, p.middle_name, p.last_name
            FROM persons p
            JOIN (
                SELECT DISTINCT first_name, middle_name, last_name FROM s
            ) sx
              ON trim(lower(p.first_name)) = trim(lower(sx.first_name))
             AND COALESCE(trim(lower(p.middle_name)), '') = COALESCE(trim(lower(sx.middle_name)), '')
             AND trim(lower(p.last_name))  = trim(lower(sx.last_name))
        )
        INSERT INTO hr_employees ({columns_to_insert})
        SELECT
            per.person_id,
            d.id
            {select_name_cols}
        FROM s
        JOIN per
          ON trim(lower(per.first_name)) = trim(lower(s.first_name))
         AND COALESCE(trim(lower(per.middle_name)), '') = COALESCE(trim(lower(s.middle_name)), '')
         AND trim(lower(per.last_name))  = trim(lower(s.last_name))
        JOIN departments d
          ON trim(lower(d.name)) = trim(lower(s.unit_slug))
        WHERE NOT EXISTS (
            SELECT 1
              FROM hr_employees e
             WHERE e.person_id    = per.person_id
               AND e.department_id = d.id
        )
    """)

    res = conn.execute(insert_sql, params)
    try:
        rc = res.rowcount if res.rowcount is not None and res.rowcount >= 0 else "unknown"
    except Exception:
        rc = "unknown"
    print(f"[seed hr_employees] Inserted rows: {rc}")


def downgrade():
    # Best-effort delete: match on person(first/middle/last) + department(unit)
    conn = op.get_bind()

    script_dir = Path(__file__).resolve().parent
    default_csv = (script_dir / "employees.csv").resolve()
    csv_path = Path(os.environ.get("HR_EMPLOYEES_SEED_CSV", str(default_csv))).resolve()

    rows = _read_seed_csv(csv_path)
    rows = [r for r in rows if r["first_name"] and r["last_name"] and r["unit"]]
    if not rows:
        print("[seed hr_employees] (downgrade) no rows → nothing to delete")
        return

    vals, params = [], {}
    for i, r in enumerate(rows):
        vals.append(f"(:f{i}, :m{i}, :l{i}, :u{i})")
        params[f"f{i}"] = r["first_name"]
        params[f"m{i}"] = r["middle_name"] or None
        params[f"l{i}"] = r["last_name"]
        params[f"u{i}"] = r["unit"]
    values_sql = ", ".join(vals)

    delete_sql = sa.text(f"""
        WITH s(first_name, middle_name, last_name, unit_slug) AS (
            VALUES {values_sql}
        ),
        per AS (
            SELECT p.id AS person_id, p.first_name, p.middle_name, p.last_name
            FROM persons p
            JOIN (
                SELECT DISTINCT first_name, middle_name, last_name FROM s
            ) sx
              ON trim(lower(p.first_name)) = trim(lower(sx.first_name))
             AND COALESCE(trim(lower(p.middle_name)), '') = COALESCE(trim(lower(sx.middle_name)), '')
             AND trim(lower(p.last_name))  = trim(lower(sx.last_name))
        ),
        targets AS (
            SELECT e.id
              FROM s
              JOIN per
                ON trim(lower(per.first_name)) = trim(lower(s.first_name))
               AND COALESCE(trim(lower(per.middle_name)), '') = COALESCE(trim(lower(s.middle_name)), '')
               AND trim(lower(per.last_name))  = trim(lower(s.last_name))
              JOIN departments d
                ON trim(lower(d.name)) = trim(lower(s.unit_slug))
              JOIN hr_employees e
                ON e.person_id    = per.person_id
               AND e.department_id = d.id
        )
        DELETE FROM hr_employees e
         USING targets t
         WHERE e.id = t.id
    """)
    conn.execute(delete_sql, params)
    print("[seed hr_employees] (downgrade) deleted seeded rows.")
