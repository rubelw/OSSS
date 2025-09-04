# versions/0022_seed_hr_employees.py
from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, List, Optional
from sqlalchemy import text
from alembic import op
import sqlalchemy as sa


revision = "0029_populate_spaces"
down_revision = "0028_populate_floors"
branch_labels = None
depends_on = None


def _get_x_arg(name: str, default: str | None = None) -> str | None:
    try:
        from alembic import context
        x = context.get_x_argument(as_dictionary=True)
        return x.get(name, default)
    except Exception:
        return default


def _resolve_csv_path() -> Path | None:
    # Allow override: alembic upgrade head -x spaces_csv=/path/to/spaces.csv
    override = _get_x_arg("spaces_csv")
    if override:
        p = Path(override)
        return p if p.exists() else None

    # Try local folder first (same dir where alembic runs)
    p1 = Path.cwd() / "spaces.csv"
    if p1.exists():
        return p1

    # Try next to this migration file
    try:
        here = Path(__file__).resolve().parent
        p2 = here / "spaces.csv"
        if p2.exists():
            return p2
    except Exception:
        pass

    return None


def _read_spaces(csv_path: Path) -> list[dict]:
    """
    Expected columns:
      - building_code (required)
      - floor_level_code (optional; if present we try to map to floors.level_code)
      - code (room number, required)
      - name
      - space_type
      - area_sqft
      - capacity
    """
    rows = []
    with csv_path.open(newline="", encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        req = {"building_code", "code"}
        if not req.issubset(set(rdr.fieldnames or [])):
            raise RuntimeError("spaces.csv must include at least building_code and code")

        for r in rdr:
            rows.append({
                "building_code": (r.get("building_code") or "").strip(),
                "level_code": (r.get("floor_level_code") or "").strip(),
                "code": (r.get("code") or "").strip(),
                "name": (r.get("name") or "").strip() or None,
                "space_type": (r.get("space_type") or "").strip() or None,
                "area_sqft": (r.get("area_sqft") or "").strip(),
                "capacity": (r.get("capacity") or "").strip(),
            })
    # Clean numeric fields
    for r in rows:
        try:
            r["area_sqft"] = float(r["area_sqft"]) if r["area_sqft"] not in ("", None) else None
        except Exception:
            r["area_sqft"] = None
        try:
            r["capacity"] = int(r["capacity"]) if r["capacity"] not in ("", None) else None
        except Exception:
            r["capacity"] = None
    return rows


def upgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"

    csv_path = _resolve_csv_path()
    if not csv_path:
        raise RuntimeError(
            "spaces.csv not found. Put it next to this migration, in CWD, "
            "or pass -x spaces_csv=/absolute/path/to/spaces.csv"
        )

    data = _read_spaces(csv_path)
    if not data:
        return

    # Build building map: code/name -> id
    b_rows = bind.execute(
        text("SELECT id, COALESCE(code, '') AS code, name FROM buildings")
    ).mappings().all()
    b_by_code = {r["code"]: str(r["id"]) for r in b_rows if r["code"]}
    b_by_name = {r["name"]: str(r["id"]) for r in b_rows if r["name"]}

    # Build floor map: (building_id, level_code) -> floor_id
    f_rows = bind.execute(
        text("SELECT id, building_id, level_code FROM floors")
    ).mappings().all()
    f_by_bld_level = {(str(r["building_id"]), (r["level_code"] or "").strip()): str(r["id"]) for r in f_rows}

    # Existing to avoid duplicates (by floor + code)
    existing = bind.execute(
        text("SELECT floor_id, code FROM spaces")
    ).mappings().all()
    existing_set = {(str(r["floor_id"]) if r["floor_id"] is not None else None, r["code"]) for r in existing}

    # Prepare insert: include building_id (derived from the matching floor) to satisfy NOT NULL constraint
    if is_pg:
        ins = text("""
            INSERT INTO spaces (building_id, floor_id, code, name, space_type, area_sqft, capacity, created_at, updated_at)
            SELECT f.building_id, :floor_id, :code, :name, :space_type, :area_sqft, :capacity, NOW(), NOW()
            FROM floors f
            WHERE f.id = :floor_id
              AND NOT EXISTS (
                  SELECT 1
                  FROM spaces s
                  WHERE s.floor_id = :floor_id
                    AND s.code = :code
              )
        """)
    else:
        # SQLite: derive building_id via floors and guard with NOT EXISTS
        ins = text("""
            INSERT INTO spaces (building_id, floor_id, code, name, space_type, area_sqft, capacity, created_at, updated_at)
            SELECT f.building_id, :floor_id, :code, :name, :space_type, :area_sqft, :capacity, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            FROM floors f
            WHERE f.id = :floor_id
              AND NOT EXISTS (
                  SELECT 1 FROM spaces s WHERE s.floor_id = :floor_id AND s.code = :code
              )
        """)

    inserted = 0
    for r in data:
        bcode = r["building_code"]
        # building lookup by code then by name
        bld_id = b_by_code.get(bcode) or b_by_name.get(bcode)
        if not bld_id:
            # building unknown; skip row
            continue

        lvl = r["level_code"]
        floor_id = None
        if lvl:
            floor_id = f_by_bld_level.get((bld_id, lvl))

        # If we can't resolve a floor, skip (schema likely needs floor_id)
        if not floor_id:
            continue

        sig = (floor_id, r["code"])
        if sig in existing_set:
            continue

        bind.execute(ins, {
            "floor_id": floor_id,
            "code": r["code"],
            "name": r["name"],
            "space_type": r["space_type"],
            "area_sqft": r["area_sqft"],
            "capacity": r["capacity"],
        })
        existing_set.add(sig)
        inserted += 1

    # Optional: print-ish message (shows up in Alembic logs)
    try:
        print(f"[populate spaces] Inserted rows: {inserted}")
    except Exception:
        pass


def downgrade() -> None:
    bind = op.get_bind()

    csv_path = _resolve_csv_path()
    if not csv_path or not csv_path.exists():
        # Safety: if we can't load the same CSV, do nothing to avoid deleting user-created data.
        return

    data = _read_spaces(csv_path)
    if not data:
        return

    # Map buildings again
    b_rows = bind.execute(text("SELECT id, COALESCE(code,'') AS code, name FROM buildings")).mappings().all()
    b_by_code = {r["code"]: str(r["id"]) for r in b_rows if r["code"]}
    b_by_name = {r["name"]: str(r["id"]) for r in b_rows if r["name"]}

    # Map floors again
    f_rows = bind.execute(text("SELECT id, building_id, level_code FROM floors")).mappings().all()
    f_by_bld_level = {(str(r["building_id"]), (r["level_code"] or "").strip()): str(r["id"]) for r in f_rows}

    # Collect exact (floor_id, code) pairs that were inserted
    pairs = []
    for r in data:
        bcode = r["building_code"]
        bld_id = b_by_code.get(bcode) or b_by_name.get(bcode)
        if not bld_id:
            continue
        lvl = r["level_code"]
        floor_id = None
        if lvl:
            floor_id = f_by_bld_level.get((bld_id, lvl))
        if not floor_id:
            continue
        pairs.append((floor_id, r["code"]))

    if not pairs:
        return

    if bind.dialect.name == "postgresql":
        # delete using a zipped unnest
        del_sql = text("""
            WITH to_del AS (
                SELECT UNNEST(:floor_ids)::uuid AS floor_id,
                       UNNEST(:codes)::text AS code
            )
            DELETE FROM spaces s
            USING to_del td
            WHERE s.floor_id = td.floor_id
              AND s.code     = td.code
        """)
        bind.execute(del_sql, {
            "floor_ids": [f for f, _ in pairs],
            "codes": [c for _, c in pairs],
        })
    else:
        # SQLite fallback: iterate
        del_one = text("DELETE FROM spaces WHERE floor_id = :fid AND code = :code")
        for fid, code in pairs:
            bind.execute(del_one, {"fid": fid, "code": code})
