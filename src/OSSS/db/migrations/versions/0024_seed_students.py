# versions/0023_create_seed_vendors.py
from __future__ import annotations

import random
import re
import uuid
from typing import List, Dict
from pathlib import Path
from datetime import datetime
import csv
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# --- Alembic identifiers
revision = "0024_seed_students"
down_revision = "0023_create_seed_vendors"
branch_labels = None
depends_on = None


def _slug(s: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")
    s = re.sub(r"-+", "-", s)
    return s or "vendor"


# ---------- helpers ----------
def _has_table(conn, table: str) -> bool:
    return table in sa.inspect(conn).get_table_names()

def _has_col(conn, table: str, column: str) -> bool:
    return any(c["name"] == column for c in sa.inspect(conn).get_columns(table))

def _parse_date(s: Optional[str]):
    """Return a date (or None) from common string formats."""
    if not s:
        return None
    s = s.strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y/%m/%d", "%m-%d-%Y", "%d-%b-%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None

def _norm_text(s: Optional[str]) -> Optional[str]:
    if s is None:
        return None
    s = s.strip()
    return s or None

def _norm_email(s: Optional[str]) -> Optional[str]:
    s = _norm_text(s)
    return s.lower() if s else None

def _norm_gender(s: Optional[str]) -> Optional[str]:
    """Map free-text gender values to a small set. Adjust to your enum if needed."""
    if not s:
        return None
    v = s.strip().lower()
    mapping = {
        "m": "male",
        "male": "male",
        "f": "female",
        "female": "female",
        "nb": "nonbinary",
        "nonbinary": "nonbinary",
        "non-binary": "nonbinary",
        "non binary": "nonbinary",
        "other": "other",
        "o": "other",
        "x": "other",
        "u": None,
        "unknown": None,
        "prefer not to say": None,
    }
    return mapping.get(v, None)

def _to_int(s: Optional[str]) -> Optional[int]:
    s = (s or "").strip()
    if not s:
        return None
    try:
        return int(s)
    except ValueError:
        return None

def _deterministic_person_id(first: str, last: str, email: Optional[str]) -> str:
    """Stable UUIDv5 so re-running won’t duplicate persons."""
    key = f"osss/person/{first}|{last}|{email or ''}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, key))

def _read_students_csv(csv_path: Path) -> List[Dict[str, Optional[str]]]:
    with csv_path.open(newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        rows: List[Dict[str, Optional[str]]] = []
        for row in r:
            rows.append(
                {
                    "first_name": _norm_text(row.get("first_name")),
                    "middle_name": _norm_text(row.get("middle_name")),
                    "last_name": _norm_text(row.get("last_name")),
                    "dob": _norm_text(row.get("dob")),
                    "email": _norm_email(row.get("email")),
                    "phone": _norm_text(row.get("phone")),
                    "gender": _norm_gender(_norm_text(row.get("gender"))),
                    "student_number": _norm_text(row.get("student_number")),
                    "graduation_year": _norm_text(row.get("graduation_year")),
                }
            )
        return rows


# ---------- migration ----------
def upgrade():
    conn = op.get_bind()

    # CSV: expects versions/student.csv next to this file
    csv_path = Path(__file__).parent / "students.csv"
    if not csv_path.exists():
        print(f"[seed students] ❌ students.csv not found at {csv_path}")
        return

    # Check required tables
    need_tables = ["persons", "students"]
    for t in need_tables:
        if not _has_table(conn, t):
            print(f"[seed students] ❌ table {t} not found — aborting")
            return

    # persons columns check
    persons_required = ["id", "first_name", "last_name"]
    missing_person_cols = [c for c in persons_required if not _has_col(conn, "persons", c)]
    if missing_person_cols:
        print(f"[seed students] ❌ persons missing columns: {missing_person_cols}")
        return

    # detect optional audit cols
    persons_has_created = _has_col(conn, "persons", "created_at")
    persons_has_updated = _has_col(conn, "persons", "updated_at")

    # students shape (we’ll write only what exists)
    st_has_person_id      = _has_col(conn, "students", "person_id")
    st_has_student_number = _has_col(conn, "students", "student_number")
    st_has_grad_year      = _has_col(conn, "students", "graduation_year")
    st_has_created        = _has_col(conn, "students", "created_at")
    st_has_updated        = _has_col(conn, "students", "updated_at")

    if not st_has_person_id:
        print("[seed students] ❌ students.person_id column is required to link to persons")
        return

    rows = _read_students_csv(csv_path)
    if not rows:
        print("[seed students] ⚠️ students.csv contained no data")
        return

    # --- Upsert persons ---
    now = datetime.utcnow()
    person_payload = []
    for r in rows:
        first, last = r["first_name"], r["last_name"]
        if not first or not last:
            continue
        pid = _deterministic_person_id(first, last, r["email"])
        person_payload.append(
            {
                "id": pid,
                "first_name": first,
                "last_name": last,
                "middle_name": r["middle_name"],
                "gender": r["gender"],
                "dob": _parse_date(r["dob"]),
                "email": r["email"],
                "phone": r["phone"],
                "created_at": now,
                "updated_at": now,
            }
        )

    if person_payload:
        cols = ["id", "first_name", "last_name", "middle_name", "gender", "dob", "email", "phone"]
        vals = [":id", ":first_name", ":last_name", ":middle_name", ":gender", ":dob", ":email", ":phone"]
        if persons_has_created:
            cols.append("created_at"); vals.append(":created_at")
        if persons_has_updated:
            cols.append("updated_at"); vals.append(":updated_at")

        upsert_persons = sa.text(
            f"""
            INSERT INTO persons ({", ".join(cols)})
            VALUES ({", ".join(vals)})
            ON CONFLICT (id) DO UPDATE
            SET
                middle_name = COALESCE(EXCLUDED.middle_name, persons.middle_name),
                gender      = COALESCE(EXCLUDED.gender, persons.gender),
                dob         = COALESCE(EXCLUDED.dob, persons.dob),
                email       = COALESCE(EXCLUDED.email, persons.email),
                phone       = COALESCE(EXCLUDED.phone, persons.phone)
                {", created_at = persons.created_at" if persons_has_created else ""}
                {", updated_at = EXCLUDED.updated_at" if persons_has_updated else ""}
            """
        )

        chunk = 500
        total = 0
        for i in range(0, len(person_payload), chunk):
            conn.execute(upsert_persons, person_payload[i : i + chunk])
            total += len(person_payload[i : i + chunk])
        print(f"[seed students] Upserted {total} persons")

    # --- Insert students ---
    # Build a VALUES list with resolved person_id + student fields
    st_rows = []
    for r in rows:
        first, last = r["first_name"], r["last_name"]
        if not first or not last:
            continue
        pid = _deterministic_person_id(first, last, r["email"])
        st_rows.append(
            {
                "person_id": pid,
                "student_number": r["student_number"],
                "graduation_year": _to_int(r["graduation_year"]),
                "created_at": now,
                "updated_at": now,
                "first_name": first,   # only for dedupe WHERE NOT EXISTS assistance if needed
                "last_name": last,
            }
        )

    if not st_rows:
        print("[seed students] ⚠️ No valid student rows after normalization")
        return

    # Compose insert columns dynamically
    insert_cols = ["person_id"]
    insert_vals = [":person_id"]
    if st_has_student_number: insert_cols.append("student_number"); insert_vals.append(":student_number")
    if st_has_grad_year:      insert_cols.append("graduation_year"); insert_vals.append(":graduation_year")
    if st_has_created:        insert_cols.append("created_at");      insert_vals.append(":created_at")
    if st_has_updated:        insert_cols.append("updated_at");      insert_vals.append(":updated_at")

    # Dedup criteria: prefer natural uniqueness if available
    # - If students has student_number, dedupe on that
    # - else dedupe on person_id
    if st_has_student_number:
        where_not_exists = "WHERE NOT EXISTS (SELECT 1 FROM students s WHERE s.student_number = :student_number)"
    else:
        where_not_exists = "WHERE NOT EXISTS (SELECT 1 FROM students s WHERE s.person_id = :person_id)"

    insert_students = sa.text(
        f"""
        INSERT INTO students ({", ".join(insert_cols)})
        SELECT {", ".join(insert_vals)}
        {where_not_exists}
        """
    )

    chunk = 500
    total = 0
    for i in range(0, len(st_rows), chunk):
        conn.execute(insert_students, st_rows[i : i + chunk])
        total += len(st_rows[i : i + chunk])

    print(f"[seed students] Inserted up to {total} students (dedup applied)")


def downgrade():
    """Best-effort removal of seeded students & related persons (safe / conservative)."""
    conn = op.get_bind()
    csv_path = Path(__file__).parent / "students.csv"
    if not csv_path.exists():
        return

    rows = _read_students_csv(csv_path)
    if not rows:
        return

    # Resolve intended person_ids and student_numbers
    ids, stu_nums = [], []
    for r in rows:
        first, last = r.get("first_name"), r.get("last_name")
        if not first or not last:
            continue
        pid = _deterministic_person_id(first, last, _norm_email(r.get("email")))
        ids.append(pid)
        if r.get("student_number"):
            stu_nums.append(r["student_number"])

    # Delete students by student_number if present; otherwise by person_id
    if stu_nums and _has_col(conn, "students", "student_number"):
        chunk = 500
        for i in range(0, len(stu_nums), chunk):
            conn.execute(
                sa.text("DELETE FROM students WHERE student_number = ANY(:nums)"),
                {"nums": stu_nums[i : i + chunk]},
            )
    elif ids and _has_col(conn, "students", "person_id"):
        chunk = 500
        for i in range(0, len(ids), chunk):
            conn.execute(
                sa.text("DELETE FROM students WHERE person_id = ANY(:ids)"),
                {"ids": ids[i : i + chunk]},
            )

    # Optionally delete persons created by this seed.
    # Comment out if you don’t want to remove persons on downgrade.
    if ids:
        chunk = 500
        for i in range(0, len(ids), chunk):
            conn.execute(
                sa.text("DELETE FROM persons WHERE id = ANY(:ids)"),
                {"ids": ids[i : i + chunk]},
            )