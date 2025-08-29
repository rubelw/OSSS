# versions/0022_seed_hr_employees.py
from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, List, Optional
from sqlalchemy import text
from alembic import op
import sqlalchemy as sa
import json
from datetime import datetime



revision = "0031_populate_parts"
down_revision = "0030_populate_assets"
branch_labels = None
depends_on = None


def _get_x_arg(key: str) -> str | None:
    from alembic import context
    try:
        xargs = context.get_x_argument(as_dictionary=True)
    except Exception:
        return None
    return xargs.get(key)


def _resolve_csv_path(default_filename: str, xarg_key: str) -> Path | None:
    override = _get_x_arg(xarg_key)
    if override:
        p = Path(override)
        return p if p.exists() else None
    here = Path(__file__).resolve().parent
    p = here / default_filename
    if p.exists():
        return p
    p = Path.cwd() / default_filename
    return p if p.exists() else None


def _read_parts(csv_path: Path) -> list[dict]:
    rows: list[dict] = []
    with csv_path.open(newline="", encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        required = {"sku", "name", "unit_cost", "uom"}
        if not required.issubset(set(rdr.fieldnames or [])):
            raise RuntimeError("parts.csv must include columns: sku, name, unit_cost, uom")
        for r in rdr:
            rows.append({
                "sku": (r.get("sku") or "").strip(),
                "name": (r.get("name") or "").strip(),
                "description": (r.get("description") or "").strip() or None,
                "unit_cost": (r.get("unit_cost") or "").strip() or None,
                "uom": (r.get("uom") or "").strip() or None,
                "attributes": (r.get("attributes") or "").strip() or None,
            })
    return rows


def upgrade() -> None:
    conn = op.get_bind()
    csv_path = _resolve_csv_path("parts.csv", "parts_csv")
    if not csv_path:
        raise RuntimeError("parts.csv not found. Pass -x parts_csv=/path/to/parts.csv")

    rows = _read_parts(csv_path)
    if not rows:
        return

    # normalize and ensure attributes is valid JSON (or null)
    def norm(r: dict) -> dict:
        attrs = r["attributes"]
        if attrs:
            try:
                json.loads(attrs)  # validate
            except Exception:
                attrs = json.dumps({"raw": attrs})
        # let Postgres cast text to numeric/jsonb with explicit CAST below
        return {
            "sku": r["sku"],
            "name": r["name"],
            "description": r["description"],
            "unit_cost": r["unit_cost"],  # text or None
            "uom": r["uom"],
            "attributes": attrs,          # JSON string or None
        }

    rows = [norm(r) for r in rows if r["sku"] and r["name"]]

    if not rows:
        return

    if conn.dialect.name == "postgresql":
        upsert = sa.text("""
            INSERT INTO parts (sku, name, description, unit_cost, uom, attributes, created_at, updated_at)
            VALUES (:sku, :name, :description, CAST(:unit_cost AS numeric), :uom, CAST(:attributes AS jsonb), NOW(), NOW())
            ON CONFLICT (sku) DO UPDATE
            SET name        = EXCLUDED.name,
                description = EXCLUDED.description,
                unit_cost   = EXCLUDED.unit_cost,
                uom         = EXCLUDED.uom,
                attributes  = COALESCE(parts.attributes, '{}'::jsonb) || COALESCE(EXCLUDED.attributes, '{}'::jsonb),
                updated_at  = NOW()
        """)
    else:
        upsert = sa.text("""
            INSERT OR REPLACE INTO parts (sku, name, description, unit_cost, uom, attributes, created_at, updated_at)
            VALUES (:sku, :name, :description, :unit_cost, :uom, :attributes, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """)

    CHUNK = 200
    for i in range(0, len(rows), CHUNK):
        conn.execute(upsert, rows[i:i+CHUNK])


def downgrade() -> None:
    conn = op.get_bind()
    csv_path = _resolve_csv_path("parts.csv", "parts_csv")
    if not csv_path:
        return
    rows = _read_parts(csv_path)
    skus = [r["sku"] for r in rows if r.get("sku")]
    if not skus:
        return

    if conn.dialect.name == "postgresql":
        conn.execute(sa.text("DELETE FROM parts WHERE sku = ANY(:skus)"), {"skus": skus})
    else:
        params = {f"sku{i}": s for i, s in enumerate(skus)}
        placeholders = ",".join(f":sku{i}" for i in range(len(skus)))
        conn.execute(sa.text(f"DELETE FROM parts WHERE sku IN ({placeholders})"), params)