# versions/0022_seed_hr_employees.py
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Dict, List, Optional
from sqlalchemy import text
from alembic import op
import sqlalchemy as sa
from datetime import datetime


revision = "0030_populate_assets"
down_revision = "0029_populate_spaces"
branch_labels = None
depends_on = None


def _get_x_arg(name: str, default: str | None = None) -> str | None:
    from alembic import context
    try:
        xargs = context.get_x_argument(as_dictionary=True)
    except Exception:
        return default
    return xargs.get(name, default)


def _resolve_csv_path(filename: str, xarg_key: str) -> Path | None:
    override = _get_x_arg(xarg_key)
    if override:
        p = Path(override)
        return p if p.exists() else None
    # same dir as migration file
    here = Path(__file__).resolve().parent
    p = here / filename
    if p.exists():
        return p
    # cwd fallback
    p = Path.cwd() / filename
    return p if p.exists() else None


def _read_assets(csv_path: Path) -> list[dict]:
    """
    Expect columns:
      building_code, space_code, tag, serial_no, manufacturer, model,
      category, status, install_date, warranty_expires_at,
      expected_life_months, attributes (JSON or blank)
    """
    out: list[dict] = []
    with csv_path.open(newline="", encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        required = {
            "building_code", "tag", "category", "status",
            "install_date", "warranty_expires_at", "expected_life_months"
        }
        if not required.issubset(set(rdr.fieldnames or [])):
            raise RuntimeError(
                f"assets.csv must include at least: {', '.join(sorted(required))}"
            )
        for row in rdr:
            # Normalize blanks to None
            d = {k: (v.strip() if isinstance(v, str) else v) for k, v in row.items()}
            d["space_code"] = d.get("space_code") or None
            d["serial_no"] = d.get("serial_no") or None
            d["manufacturer"] = d.get("manufacturer") or None
            d["model"] = d.get("model") or None
            # parse ints/dates if present (keep date strings; DB will cast)
            d["expected_life_months"] = int(d["expected_life_months"]) if d.get("expected_life_months") else None
            d["install_date"] = d["install_date"] or None
            d["warranty_expires_at"] = d["warranty_expires_at"] or None
            # attributes JSON
            attrs_raw = d.get("attributes")
            if attrs_raw:
                try:
                    d["attributes"] = json.loads(attrs_raw)
                except Exception:
                    d["attributes"] = None
            else:
                d["attributes"] = None
            out.append(d)
    return out


def upgrade() -> None:
    conn = op.get_bind()
    csv_path = _resolve_csv_path("assets.csv", "assets_csv")
    if not csv_path:
        raise RuntimeError("assets.csv not found. Pass -x assets_csv=/path/to/assets.csv")

    rows = _read_assets(csv_path)
    if not rows:
        return

    is_pg = conn.dialect.name == "postgresql"

    # Build building lookup (by code and name)
    bld_rows = conn.execute(
        text("SELECT id, COALESCE(code,'') AS code, name FROM buildings")
    ).mappings().all()
    bld_by_code = {r["code"]: str(r["id"]) for r in bld_rows if r["code"]}
    bld_by_name = {r["name"]: str(r["id"]) for r in bld_rows if r["name"]}

    # Build space lookup by (building_id, code) via floors (spaces has floor_id)
    sp_rows = conn.execute(text("""
        SELECT
            s.id          AS space_id,
            f.building_id AS building_id,
            s.code        AS space_code
        FROM spaces s
        LEFT JOIN floors f ON f.id = s.floor_id
    """)).mappings().all()
    space_by_bld_code: dict[str, dict[str, str]] = {}
    for r in sp_rows:
        bid = str(r["building_id"]) if r["building_id"] is not None else None
        if not bid:
            continue
        inner = space_by_bld_code.setdefault(bid, {})
        inner[r["space_code"]] = str(r["space_id"])

    # Prepare insert (PG casts :attributes via CAST to jsonb)
    insert_sql = text(
        """
        INSERT INTO assets (
            building_id, space_id, parent_asset_id,
            tag, serial_no, manufacturer, model, category, status,
            install_date, warranty_expires_at, expected_life_months,
            attributes, created_at, updated_at
        )
        VALUES (
            :building_id, :space_id, :parent_asset_id,
            :tag, :serial_no, :manufacturer, :model, :category, :status,
            :install_date, :warranty_expires_at, :expected_life_months,
            CAST(:attributes AS JSONB), NOW(), NOW()
        )
        ON CONFLICT (tag) DO NOTHING
        """
    ) if is_pg else text(
        """
        INSERT OR IGNORE INTO assets (
            building_id, space_id, parent_asset_id,
            tag, serial_no, manufacturer, model, category, status,
            install_date, warranty_expires_at, expected_life_months,
            attributes, created_at, updated_at
        )
        VALUES (
            :building_id, :space_id, :parent_asset_id,
            :tag, :serial_no, :manufacturer, :model, :category, :status,
            :install_date, :warranty_expires_at, :expected_life_months,
            :attributes, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
        )
        """
    )

    inserted = 0
    for r in rows:
        bcode = r.get("building_code")
        building_id = bld_by_code.get(bcode) or bld_by_name.get(bcode)
        if not building_id:
            # skip if unknown building
            continue

        # resolve space (optional)
        space_id = None
        scode = r.get("space_code")
        if scode:
            inner = space_by_bld_code.get(building_id) or {}
            space_id = inner.get(scode)

        # Always serialize attributes; PG will CAST to jsonb above
        attrs = r.get("attributes")
        attrs_param = json.dumps(attrs) if attrs is not None else None

        params = {
            "building_id": building_id,
            "space_id": space_id,
            "parent_asset_id": None,
            "tag": r["tag"],
            "serial_no": r.get("serial_no"),
            "manufacturer": r.get("manufacturer"),
            "model": r.get("model"),
            "category": r.get("category"),
            "status": r.get("status"),
            "install_date": r.get("install_date"),
            "warranty_expires_at": r.get("warranty_expires_at"),
            "expected_life_months": r.get("expected_life_months"),
            "attributes": attrs_param,
        }

        conn.execute(insert_sql, params)
        inserted += 1

    # Optional: print-ish progress hint (shows up in logs)
    try:
        conn.execute(text("SELECT 1"))
        print(f"[populate assets] Insert attempted for {inserted} rows from {csv_path.name}")
    except Exception:
        pass


def downgrade() -> None:
    conn = op.get_bind()
    csv_path = _resolve_csv_path("assets.csv", "assets_csv")
    if not csv_path:
        # No file to know which tags—do nothing to avoid accidental deletion.
        return

    rows = _read_assets(csv_path)
    if not rows:
        return

    tags = [r["tag"] for r in rows if r.get("tag")]
    if not tags:
        return

    if conn.dialect.name == "postgresql":
        conn.execute(text("DELETE FROM assets WHERE tag = ANY(:tags)"), {"tags": tags})
    else:
        # SQLite
        placeholders = ",".join([f":t{i}" for i in range(len(tags))])
        params = {f"t{i}": t for i, t in enumerate(tags)}
        conn.execute(text(f"DELETE FROM assets WHERE tag IN ({placeholders})"), params)
