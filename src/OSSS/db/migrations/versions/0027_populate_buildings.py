# versions/0022_seed_hr_employees.py
from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, List, Optional
from sqlalchemy import text
from alembic import op
import sqlalchemy as sa


revision = "0027_populate_buildings"
down_revision = "0026_seed_facilities_table"
branch_labels = None
depends_on = None


def _get_x_arg(name: str, default: str | None = None) -> str | None:
    """Read a -x key=value argument passed to Alembic."""
    from alembic import context
    try:
        xargs = context.get_x_argument(as_dictionary=True)
    except Exception:
        return default
    return xargs.get(name, default)


def _resolve_csv_path(default_name: str, xarg_key: str) -> Path | None:
    """
    Resolve CSV path by precedence:
      1) -x buildings_csv=/path/to/file.csv
      2) file next to this migration (versions/<this>.py -> versions/buildings.csv)
      3) current working directory
    """
    override = _get_x_arg(xarg_key)
    if override:
        p = Path(override)
        return p if p.exists() else None

    here = Path(__file__).parent / default_name
    if here.exists():
        return here

    cwd = Path.cwd() / default_name
    if cwd.exists():
        return cwd

    return None


def _read_rows(csv_path: Path) -> list[dict]:
    """
    Expected header columns (case-sensitive):
      facility_code, facility_name, name, code, year_built, floors_count, gross_sqft,
      use_type, address, attributes

    'address' and 'attributes' should be JSON strings; they are optional.
    """
    rows: list[dict] = []
    with csv_path.open(newline="", encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        required = {"name", "code"}
        if not required.issubset(set(rdr.fieldnames or [])):
            raise RuntimeError("buildings.csv must at least include columns: name, code")

        for row in rdr:
            rows.append({k: (v.strip() if isinstance(v, str) else v) for k, v in row.items()})
    return rows


def upgrade() -> None:
    bind = op.get_bind()

    csv_path = _resolve_csv_path("buildings.csv", "buildings_csv")
    if not csv_path:
        raise RuntimeError(
            "buildings.csv not found. Put it next to this migration or pass -x buildings_csv=/abs/path.csv"
        )

    rows = _read_rows(csv_path)
    if not rows:
        return

    # facilities lookup (by code preferred, then by name)
    fac_rows = bind.execute(text("SELECT id, code, name FROM facilities")).mappings().all()
    fac_by_code = {r["code"]: str(r["id"]) for r in fac_rows if r.get("code")}
    fac_by_name = {r["name"].strip().lower(): str(r["id"]) for r in fac_rows if r.get("name")}

    # existing building codes for idempotency
    existing_codes = {
        r["code"] for r in bind.execute(text("SELECT code FROM buildings")).mappings().all() if r.get("code")
    }

    is_pg = bind.dialect.name == "postgresql"

    if is_pg:
        upsert = text(
            """
            INSERT INTO buildings
                (facility_id, name, code, year_built, floors_count, gross_sqft, use_type, address, attributes, created_at, updated_at)
            VALUES
                (:facility_id, :name, :code, :year_built, :floors_count, :gross_sqft, :use_type, :address, :attributes, NOW(), NOW())
            ON CONFLICT (code) DO UPDATE
            SET facility_id = EXCLUDED.facility_id,
                name        = EXCLUDED.name,
                year_built  = EXCLUDED.year_built,
                floors_count= EXCLUDED.floors_count,
                gross_sqft  = EXCLUDED.gross_sqft,
                use_type    = EXCLUDED.use_type,
                address     = EXCLUDED.address,
                attributes  = EXCLUDED.attributes,
                updated_at  = NOW()
            """
        )
    else:
        upsert = text(
            """
            INSERT OR REPLACE INTO buildings
                (facility_id, name, code, year_built, floors_count, gross_sqft, use_type, address, attributes, created_at, updated_at)
            VALUES
                (:facility_id, :name, :code, :year_built, :floors_count, :gross_sqft, :use_type, :address, :attributes, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """
        )

    to_insert = []
    for r in rows:
        if r.get("code") in existing_codes and is_pg is False:
            # For SQLite we REPLACE anyway, but keep behavior consistent by allowing.
            pass

        fac_id = None
        fac_code = (r.get("facility_code") or "").strip() or None
        fac_name = (r.get("facility_name") or "").strip() or None
        if fac_code and fac_code in fac_by_code:
            fac_id = fac_by_code[fac_code]
        elif fac_name and fac_name.lower() in fac_by_name:
            fac_id = fac_by_name[fac_name.lower()]

        if not fac_id:
            # Skip rows we can't map to a facility
            continue

        # Parse JSON cells if present
        def _parse_json(val):
            if val is None or val == "":
                return None
            try:
                return json.loads(val)
            except Exception:
                # Store as text fallback to avoid failing the whole migration
                return val

        to_insert.append(
            {
                "facility_id": fac_id,
                "name": r.get("name"),
                "code": r.get("code"),
                "year_built": int(r["year_built"]) if (r.get("year_built") or "").isdigit() else None,
                "floors_count": int(r["floors_count"]) if (r.get("floors_count") or "").isdigit() else None,
                "gross_sqft": float(r["gross_sqft"]) if (r.get("gross_sqft") or "").replace(".","",1).isdigit() else None,
                "use_type": r.get("use_type"),
                "address": _parse_json(r.get("address")),
                "attributes": _parse_json(r.get("attributes")),
            }
        )

    if not to_insert:
        return

    # Use executemany
    bind.execute(upsert, to_insert)


def downgrade() -> None:
    bind = op.get_bind()
    csv_path = _resolve_csv_path("buildings.csv", "buildings_csv")
    if not csv_path:
        # If we don't know which codes we inserted, be conservative and do nothing.
        return

    rows = _read_rows(csv_path)
    codes = [r["code"] for r in rows if r.get("code")]

    if not codes:
        return

    if bind.dialect.name == "postgresql":
        bind.execute(
            text("DELETE FROM buildings WHERE code = ANY(:codes)"),
            {"codes": codes},
        )
    else:
        # SQLite fallback
        marks = ",".join([f":c{i}" for i in range(len(codes))])
        params = {f"c{i}": c for i, c in enumerate(codes)}
        bind.execute(text(f"DELETE FROM buildings WHERE code IN ({marks})"), params)