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



revision = "0032_populate_asset_parts"
down_revision = "0031_populate_parts"
branch_labels = None
depends_on = None


def _get_x_arg(key: str) -> Optional[str]:
    from alembic import context
    try:
        x = context.get_x_argument(as_dictionary=True)
    except Exception:
        return None
    return x.get(key)


def _resolve_csv_path(default_filename: str, xarg_key: str) -> Optional[Path]:
    override = _get_x_arg(xarg_key)
    if override:
        p = Path(override)
        if p.exists():
            return p
    here = Path(__file__).resolve().parent
    p = here / default_filename
    if p.exists():
        return p
    p = Path.cwd() / default_filename
    return p if p.exists() else None


def _read_asset_parts(csv_path: Path) -> List[dict]:
    """
    Expect columns:
      - asset_tag (optional)
      - asset_category (optional)
      - part_sku (required)
      - qty (optional numeric, defaults to 1)
    """
    rows: List[dict] = []
    with csv_path.open(newline="", encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        required_any = {"asset_tag", "asset_category"}
        if "part_sku" not in (rdr.fieldnames or []):
            raise RuntimeError("asset_parts.csv must have column: part_sku")
        if not required_any.intersection(set(rdr.fieldnames or [])):
            raise RuntimeError("asset_parts.csv must have either asset_tag or asset_category (or both).")
        for r in rdr:
            tag = (r.get("asset_tag") or "").strip()
            cat = (r.get("asset_category") or "").strip()
            sku = (r.get("part_sku") or "").strip()
            qty = (r.get("qty") or "").strip()
            rows.append(
                {
                    "asset_tag": tag or None,
                    "asset_category": cat or None,
                    "part_sku": sku,
                    "qty": qty or "1",
                }
            )
    # Keep only rows with a SKU and at least tag or category
    rows = [r for r in rows if r["part_sku"] and (r["asset_tag"] or r["asset_category"])]
    return rows


def upgrade() -> None:
    conn = op.get_bind()

    csv_path = _resolve_csv_path("asset_parts.csv", "asset_parts_csv")
    if not csv_path:
        raise RuntimeError("asset_parts.csv not found. Pass -x asset_parts_csv=/path/to/asset_parts.csv")

    src = _read_asset_parts(csv_path)
    if not src:
        return

    # Prefetch assets: map by tag, and by category (lowercased)
    asset_rows = conn.execute(text("SELECT id, tag, category FROM assets")).mappings().all()
    assets_by_tag: Dict[str, str] = { (r["tag"] or "").strip(): str(r["id"]) for r in asset_rows if r.get("tag") }
    assets_by_cat: Dict[str, List[str]] = {}
    for r in asset_rows:
        cat = (r["category"] or "").strip().lower()
        if not cat:
            continue
        assets_by_cat.setdefault(cat, []).append(str(r["id"]))

    # Prefetch parts by SKU
    part_rows = conn.execute(text("SELECT id, sku FROM parts")).mappings().all()
    parts_by_sku: Dict[str, str] = { (r["sku"] or "").strip(): str(r["id"]) for r in part_rows if r.get("sku") }

    # Build target insert rows; de-dupe by (asset_id, part_id)
    to_insert: List[dict] = []
    seen: Set[Tuple[str, str]] = set()

    def add_pair(asset_id: str, part_id: str, qty: str) -> None:
        key = (asset_id, part_id)
        if key in seen:
            return
        seen.add(key)
        to_insert.append({"asset_id": asset_id, "part_id": part_id, "qty": qty})

    for r in src:
        sku = r["part_sku"]
        part_id = parts_by_sku.get(sku)
        if not part_id:
            continue

        qty = r["qty"] or "1"

        if r["asset_tag"]:
            aid = assets_by_tag.get(r["asset_tag"])
            if aid:
                add_pair(aid, part_id, qty)
            # else: skip unknown tag silently (idempotent)
        elif r["asset_category"]:
            cat_key = r["asset_category"].strip().lower()
            for aid in assets_by_cat.get(cat_key, []):
                add_pair(aid, part_id, qty)

    if not to_insert:
        return

    is_pg = conn.dialect.name == "postgresql"
    if is_pg:
        stmt = sa.text("""
            INSERT INTO asset_parts (asset_id, part_id, qty, created_at, updated_at)
            VALUES (:asset_id, :part_id, CAST(:qty AS numeric), NOW(), NOW())
            ON CONFLICT (asset_id, part_id) DO NOTHING
        """)
    else:
        stmt = sa.text("""
            INSERT OR IGNORE INTO asset_parts (asset_id, part_id, qty, created_at, updated_at)
            VALUES (:asset_id, :part_id, :qty, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """)

    CHUNK = 500
    for i in range(0, len(to_insert), CHUNK):
        conn.execute(stmt, to_insert[i:i+CHUNK])


def downgrade() -> None:
    conn = op.get_bind()
    csv_path = _resolve_csv_path("asset_parts.csv", "asset_parts_csv")
    if not csv_path:
        # Can't safely determine which pairs to remove; bail out quietly.
        return

    src = _read_asset_parts(csv_path)
    if not src:
        return

    # Recompute the same lookups as in upgrade()
    asset_rows = conn.execute(text("SELECT id, tag, category FROM assets")).mappings().all()
    assets_by_tag = { (r["tag"] or "").strip(): str(r["id"]) for r in asset_rows if r.get("tag") }
    assets_by_cat: Dict[str, List[str]] = {}
    for r in asset_rows:
        cat = (r["category"] or "").strip().lower()
        if not cat:
            continue
        assets_by_cat.setdefault(cat, []).append(str(r["id"]))

    part_rows = conn.execute(text("SELECT id, sku FROM parts")).mappings().all()
    parts_by_sku = { (r["sku"] or "").strip(): str(r["id"]) for r in part_rows if r.get("sku") }

    pairs: Set[Tuple[str, str]] = set()
    for r in src:
        part_id = parts_by_sku.get((r["part_sku"] or "").strip())
        if not part_id:
            continue
        if r["asset_tag"]:
            aid = assets_by_tag.get(r["asset_tag"])
            if aid:
                pairs.add((aid, part_id))
        elif r["asset_category"]:
            cat_key = r["asset_category"].strip().lower()
            for aid in assets_by_cat.get(cat_key, []):
                pairs.add((aid, part_id))

    if not pairs:
        return

    # Delete one pair at a time (dataset is small)
    if conn.dialect.name == "postgresql":
        del_stmt = sa.text("""
            DELETE FROM asset_parts
            WHERE asset_id = :aid AND part_id = :pid
        """)
    else:
        del_stmt = sa.text("DELETE FROM asset_parts WHERE asset_id = :aid AND part_id = :pid")

    for aid, pid in pairs:
        conn.execute(del_stmt, {"aid": aid, "pid": pid})