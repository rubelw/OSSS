# versions/0023_create_seed_vendors.py
from __future__ import annotations

import csv
import uuid
from pathlib import Path
from typing import List, Dict, Optional

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# --- Alembic identifiers
revision = "0023_create_seed_vendors"
down_revision = "0022_seed_hr_employees"
branch_labels = None
depends_on = None


def _get_x_arg(name: str, default: Optional[str] = None) -> Optional[str]:
    """Read a -x key=value arg passed to Alembic (e.g., -x vendors_csv=/path/to/vendors.csv)."""
    try:
        from alembic import context
        xargs = context.get_x_argument(as_dictionary=True)
        return xargs.get(name, default)
    except Exception:
        return default


def _resolve_csv_path(filename: str = "vendors.csv", xarg_key: str = "vendors_csv") -> Optional[Path]:
    """
    Resolve CSV path via:
      1) -x vendors_csv=/path/to/file.csv
      2) next to this migration
      3) current working directory
    """
    override = _get_x_arg(xarg_key)
    if override:
        p = Path(override).expanduser().resolve()
        if p.exists():
            return p

    here = Path(__file__).resolve().parent / filename
    if here.exists():
        return here

    cwd = Path.cwd() / filename
    if cwd.exists():
        return cwd

    return None


def _parse_bool(s: str | None) -> bool:
    return str(s).strip().lower() in {"1", "true", "t", "yes", "y"}


def _read_vendors(csv_path: Path) -> List[Dict]:
    """
    Expect columns:
      - id (optional; UUID). If missing/blank, we derive uuid5 from name.
      - name (required)
      - contact_name, contact_email, contact_phone (optional but recommended)
      - active (optional; defaults true)  -> 'true'/'false'/'1'/'0' etc.
      - notes (optional)
    """
    rows: List[Dict] = []
    with csv_path.open(newline="", encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        required = {"name"}
        if not required.issubset(set(rdr.fieldnames or [])):
            raise RuntimeError("vendors.csv must include at least a 'name' column")

        for r in rdr:
            name = (r.get("name") or "").strip()
            if not name:
                continue

            vid = (r.get("id") or "").strip()
            if not vid:
                vid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"osss/vendor/{name}"))

            contact = {
                "name": (r.get("contact_name") or "").strip() or None,
                "email": (r.get("contact_email") or "").strip() or None,
                "phone": (r.get("contact_phone") or "").strip() or None,
            }
            # Remove None keys for cleaner JSON
            contact = {k: v for k, v in contact.items() if v is not None}

            active = True if r.get("active") is None else _parse_bool(r.get("active"))
            notes = (r.get("notes") or "").strip() or None

            rows.append(
                {
                    "id": vid,
                    "name": name,
                    "contact": contact,
                    "active": active,
                    "notes": notes,
                }
            )
    return rows


def upgrade():
    # Ensure gen_random_uuid() is available (harmless if already there)
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    csv_path = _resolve_csv_path()
    if not csv_path:
        raise RuntimeError(
            "vendors.csv not found. Place it next to this migration or pass -x vendors_csv=/path/to/vendors.csv"
        )

    rows = _read_vendors(csv_path)
    if not rows:
        # Nothing to insert
        return

    conn = op.get_bind()
    is_pg = conn.dialect.name == "postgresql"

    insert_sql = sa.text(
        """
        INSERT INTO vendors (id, name, contact, active, notes)
        VALUES (:id, :name, :contact, :active, :notes)
        ON CONFLICT (name) DO NOTHING
        """
    ).bindparams(
        sa.bindparam("id"),
        sa.bindparam("name"),
        sa.bindparam("contact", type_=JSONB if is_pg else sa.JSON),
        sa.bindparam("active"),
        sa.bindparam("notes"),
    )

    # Insert in manageable chunks
    CHUNK = 200
    for i in range(0, len(rows), CHUNK):
        conn.execute(insert_sql, rows[i : i + CHUNK])


def downgrade():
    # Delete vendors that match names present in the CSV (safer than dropping the table)
    csv_path = _resolve_csv_path()
    if not csv_path:
        return
    names = [r["name"] for r in _read_vendors(csv_path)]
    if not names:
        return

    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        conn.execute(
            sa.text("DELETE FROM vendors WHERE name = ANY(:names)"),
            {"names": names},
        )
    else:
        # Generic fallback
        placeholders = ",".join([f":n{i}" for i in range(len(names))])
        params = {f"n{i}": n for i, n in enumerate(names)}
        conn.execute(sa.text(f"DELETE FROM vendors WHERE name IN ({placeholders})"), params)
