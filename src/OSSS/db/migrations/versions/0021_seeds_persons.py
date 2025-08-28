# versions/0021_seed_persons.py
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from pathlib import Path
import csv
import uuid
from datetime import datetime
from typing import Optional, List, Dict


# Alembic identifiers
revision = "0021_seed_persons"
down_revision = "0020_seed_dept_position_index"
branch_labels = None
depends_on = None


# ---------- helpers ----------
def _parse_date(s: Optional[str]):
    """Return a date object (or None) from common string formats."""
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
    return None  # leave unparsed dates as NULL


def _norm_text(s: Optional[str]) -> Optional[str]:
    if s is None:
        return None
    s = s.strip()
    return s or None


def _norm_email(s: Optional[str]) -> Optional[str]:
    s = _norm_text(s)
    return s.lower() if s else None


def _norm_gender(s: Optional[str]) -> Optional[str]:
    """
    Map free-text gender values to a small set. Adjust to your enum if needed.
    """
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


def _deterministic_person_id(first: str, last: str, email: Optional[str]) -> str:
    """
    Generate a stable UUIDv5 so re-running the migration won't duplicate rows.
    Email may be missing; (first,last) still yields a stable ID.
    """
    key = f"osss/person/{first}|{last}|{email or ''}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, key))


def _has_col(conn, table: str, column: str) -> bool:
    insp = sa.inspect(conn)
    return any(c["name"] == column for c in insp.get_columns(table))


def _read_employees_csv(csv_path: Path) -> List[Dict[str, Optional[str]]]:
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
                    "email": _norm_text(row.get("email")),
                    "phone": _norm_text(row.get("phone")),
                    "gender": _norm_text(row.get("gender")),
                    "unit": _norm_text(row.get("unit")),  # parsed but not stored in persons
                }
            )
        return rows


# ---------- migration ----------
def upgrade():
    conn = op.get_bind()

    csv_path = Path(__file__).parent / "employees.csv"
    if not csv_path.exists():
        print(f"[seed persons] ❌ employees.csv not found at {csv_path}")
        return

    # Check persons table shape
    must_have = ["id", "first_name", "last_name"]
    missing = [c for c in must_have if not _has_col(conn, "persons", c)]
    if missing:
        print(f"[seed persons] ❌ persons table missing required columns: {missing}")
        return

    rows = _read_employees_csv(csv_path)
    if not rows:
        print("[seed persons] ⚠️ employees.csv contained no data")
        return

    # Build payload (normalize + deterministic IDs)
    payload = []
    now = datetime.utcnow()
    for r in rows:
        first = r["first_name"]
        last = r["last_name"]
        if not first or not last:
            continue
        email = _norm_email(r["email"])
        payload.append(
            {
                "id": _deterministic_person_id(first, last, email),
                "first_name": first,
                "last_name": last,
                "middle_name": r["middle_name"],
                "gender": _norm_gender(r["gender"]),
                "dob": _parse_date(r["dob"]),
                "email": email,
                "phone": r["phone"],
                "created_at": now,
                "updated_at": now,
            }
        )

    if not payload:
        print("[seed persons] ⚠️ No valid rows to insert after normalization")
        return

    # Build INSERT ... ON CONFLICT dynamically to include created/updated if present
    has_created = _has_col(conn, "persons", "created_at")
    has_updated = _has_col(conn, "persons", "updated_at")

    cols = ["id", "first_name", "last_name", "middle_name", "gender", "dob", "email", "phone"]
    vals = [":id", ":first_name", ":last_name", ":middle_name", ":gender", ":dob", ":email", ":phone"]

    if has_created:
        cols.append("created_at")
        vals.append(":created_at")
    if has_updated:
        cols.append("updated_at")
        vals.append(":updated_at")

    insert_sql = sa.text(
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
            {", created_at = persons.created_at" if has_created else ""}
            {", updated_at = EXCLUDED.updated_at" if has_updated else ""}
        """
    )

    # Chunked execute
    chunk = 500
    total = 0
    for i in range(0, len(payload), chunk):
        conn.execute(insert_sql, payload[i : i + chunk])
        total += len(payload[i : i + chunk])

    print(f"[seed persons] Upserted {total} rows into persons (parsed unit column but did not store it)")


def downgrade():
    """Delete seeded persons based on deterministic IDs recomputed from CSV."""
    conn = op.get_bind()
    csv_path = Path(__file__).parent / "employees.csv"
    if not csv_path.exists():
        return

    rows = _read_employees_csv(csv_path)
    ids = []
    for r in rows:
        first = r.get("first_name")
        last = r.get("last_name")
        if not first or not last:
            continue
        email = _norm_email(r.get("email"))
        ids.append(_deterministic_person_id(first, last, email))

    if not ids:
        return

    chunk = 500
    for i in range(0, len(ids), chunk):
        conn.execute(sa.text("DELETE FROM persons WHERE id = ANY(:ids)"), {"ids": ids[i : i + chunk]})
