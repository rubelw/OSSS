from __future__ import annotations

import os
import csv
from pathlib import Path
from typing import Optional

from alembic import op, context
import sqlalchemy as sa

# --- Alembic identifiers ---
revision = "0005_populate_schools_table"
down_revision = "0004_populate_orgs_table"
branch_labels = None
depends_on = None

# Official district code for Dallas Center–Grimes
DCG_CODE = "15760000"

def _log(msg: str) -> None:
    print(f"[{revision}] {msg}")

def _resolve_csv_path() -> Path:
    """
    Look for schools.csv in the following order:
      1) -x schools_csv=/path/to/schools.csv
      2) $SCHOOLS_CSV environment variable
      3) Same folder as this migration file
      4) a sibling 'data/schools.csv' folder
    """
    x = context.get_x_argument(as_dictionary=True)
    if "schools_csv" in x:
        p = Path(x["schools_csv"]).expanduser().resolve()
        if p.exists():
            _log(f"Using CSV from -x schools_csv={p}")
            return p
        raise RuntimeError(f"CSV not found at -x schools_csv={p}")

    env = os.getenv("SCHOOLS_CSV")
    if env:
        p = Path(env).expanduser().resolve()
        if p.exists():
            _log(f"Using CSV from $SCHOOLS_CSV={p}")
            return p
        raise RuntimeError(f"CSV not found at $SCHOOLS_CSV={p}")

    here = Path(__file__).resolve().parent
    for cand in (here / "schools.csv", here / "data" / "schools.csv"):
        if cand.exists():
            _log(f"Using CSV located next to migration: {cand}")
            return cand

    raise RuntimeError(
        "schools.csv not found. Place it next to this migration, in a local "
        "'data' subfolder, set $SCHOOLS_CSV, or pass -x schools_csv=/path/to/file.csv"
    )

def _find_organization_id(conn) -> Optional[str]:
    # 1) Try code (most reliable)
    did = conn.scalar(sa.text("SELECT id FROM organizations WHERE code = :c"), {"c": DCG_CODE})
    if did:
        _log(f"Matched organization by code={DCG_CODE} -> {did}")
        return did

    # 2) Try several name variants
    exact_candidates = [
        "Dallas Center-Grimes",
        "Dallas Center–Grimes",  # en dash
        "Dallas Center Grimes",
        "Dallas Center-Grimes Community School District",
        "Dallas Center–Grimes Community School District",
    ]
    for cand in exact_candidates:
        did = conn.scalar(sa.text("SELECT id FROM organizations WHERE name = :n"), {"n": cand})
        if did:
            _log(f"Matched organization by exact name '{cand}' -> {did}")
            return did

    # 3) Fallback fuzzy
    did = conn.scalar(
        sa.text(
            "SELECT id FROM organizations "
            "WHERE name ILIKE '%Dallas Center%' AND name ILIKE '%Grimes%' "
            "ORDER BY LENGTH(name) ASC LIMIT 1"
        )
    )
    if did:
        _log(f"Matched organization by fuzzy ILIKE -> {did}")
    else:
        _log("Organization lookup failed (Dallas Center–Grimes not found).")
    return did

def upgrade():
    conn = op.get_bind()

    # Ensure gen_random_uuid() exists (pgcrypto) & columns exist (idempotent)
    conn.execute(sa.text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
    conn.execute(sa.text("ALTER TABLE schools ADD COLUMN IF NOT EXISTS nces_school_id TEXT"))
    conn.execute(sa.text("ALTER TABLE schools ADD COLUMN IF NOT EXISTS building_code  TEXT"))
    conn.execute(sa.text("ALTER TABLE schools ADD COLUMN IF NOT EXISTS school_code   TEXT"))
    _log("Ensured columns nces_school_id, building_code, school_code on schools.")

    organization_id = _find_organization_id(conn)
    if not organization_id:
        raise RuntimeError(
            "Organization for Dallas Center–Grimes not found. "
            "Verify organizations table has code=15760000 or a compatible name."
        )

    csv_path = _resolve_csv_path()
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = []
        for i, row in enumerate(reader, 1):
            name = (row.get("name") or "").strip()
            nces = (row.get("nces_school_id") or "").strip()
            bcode = (row.get("building_code") or "").strip()
            if not name:
                _log(f"Skipping row {i}: missing 'name'")
                continue
            rows.append({"name": name, "nces": nces, "bcode": bcode})

    sel_id_sql = sa.text("SELECT id FROM schools WHERE organization_id = :d AND name = :n")
    upd_sql = sa.text(
        "UPDATE schools "
        "   SET nces_school_id = :nces, "
        "       building_code  = :bcode, "
        "       school_code    = COALESCE(school_code, :bcode), "
        "       updated_at     = NOW() "
        " WHERE id = :id"
    )
    ins_sql = sa.text(
        "INSERT INTO schools "
        "    (id, organization_id, name, nces_school_id, building_code, school_code, created_at, updated_at) "
        "VALUES (gen_random_uuid(), :d, :n, :nces, :bcode, :bcode, NOW(), NOW())"
    )

    inserted = updated = 0
    for r in rows:
        existing_id = conn.scalar(sel_id_sql, {"d": organization_id, "n": r["name"]})
        if existing_id:
            conn.execute(upd_sql, {"id": existing_id, "nces": r["nces"], "bcode": r["bcode"]})
            updated += 1
            _log(f"Updated: {r['name']} (id={existing_id}) nces={r['nces']} bcode={r['bcode']}")
        else:
            conn.execute(ins_sql, {"d": organization_id, "n": r["name"], "nces": r["nces"], "bcode": r["bcode"]})
            inserted += 1
            _log(f"Inserted: {r['name']} nces={r['nces']} bcode={r['bcode']}")

    # Post-check
    count = conn.scalar(sa.text("SELECT COUNT(*) FROM schools WHERE organization_id = :d"), {"d": organization_id})
    _log(f"Done. Inserted={inserted}, Updated={updated}, OrganizationRowCount={count}")

def downgrade():
    conn = op.get_bind()
    organization_id = _find_organization_id(conn)
    if not organization_id:
        _log("Downgrade: organization not found; skipping.")
        return

    csv_path = _resolve_csv_path()
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        names = [ (row.get("name") or "").strip() for row in reader if (row.get("name") or "").strip() ]

    upd_null_sql = sa.text(
        "UPDATE schools "
        "   SET nces_school_id = NULL, building_code = NULL, updated_at = NOW() "
        " WHERE organization_id = :d AND name = :n"
    )
    for name in names:
        conn.execute(upd_null_sql, {"d": organization_id, "n": name})
        _log(f"Cleared fields on: {name}")
