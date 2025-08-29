# versions/0022_seed_hr_employees.py
from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, List, Optional
from sqlalchemy import text
from alembic import op
import sqlalchemy as sa


revision = "0028_populate_floors"
down_revision = "0027_populate_buildings"
branch_labels = None
depends_on = None


def _get_x_arg(key: str, default: str | None = None) -> str | None:
    from alembic import context
    x = context.get_x_argument(as_dictionary=True)
    return x.get(key, default)


def _resolve_csv_path(filename: str, xarg_key: str) -> Path | None:
    override = _get_x_arg(xarg_key)
    if override:
        p = Path(override)
        return p if p.exists() else None
    # try alongside the migration file (versions/) and CWD
    cwd = Path.cwd() / filename
    if cwd.exists():
        return cwd
    here = Path(__file__).resolve().parent / filename
    return here if here.exists() else None


def _read_floors(csv_path: Path) -> list[dict]:
    """Expect columns: building_code, level_code, name"""
    rows: list[dict] = []
    with csv_path.open(newline="", encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        req = {"building_code", "level_code", "name"}
        if not req.issubset(set(rdr.fieldnames or [])):
            raise RuntimeError("floors.csv must have columns: building_code, level_code, name")
        for r in rdr:
            rows.append(
                {
                    "building_code": (r.get("building_code") or "").strip(),
                    "level_code": (r.get("level_code") or "").strip(),
                    "name": (r.get("name") or "").strip(),
                }
            )
    return [r for r in rows if r["building_code"] and r["level_code"]]


def upgrade() -> None:
    conn = op.get_bind()

    csv_path = _resolve_csv_path("floors.csv", "floors_csv")
    if not csv_path:
        raise RuntimeError("floors.csv not found. Pass -x floors_csv=/path/to/floors.csv")
    rows = _read_floors(csv_path)
    if not rows:
        return

    # Map building identifiers -> id (prefer code, fallback to name)
    bld = conn.execute(
        text("SELECT id, code, name FROM buildings")
    ).mappings().all()
    id_by_code = { (r["code"] or "").strip(): str(r["id"]) for r in bld if r.get("code") }
    id_by_name = { (r["name"] or "").strip(): str(r["id"]) for r in bld if r.get("name") }

    # Existing floors (building_id, level_code) to stay idempotent
    existing_pairs = {
        (str(r["building_id"]), (r["level_code"] or "").strip())
        for r in conn.execute(text("SELECT building_id, level_code FROM floors")).mappings()
    }

    insert_stmt = text(
        """
        INSERT INTO floors (building_id, level_code, name, created_at, updated_at)
        VALUES (:building_id, :level_code, :name, NOW(), NOW())
        """
    )

    to_add = 0
    for r in rows:
        bid = id_by_code.get(r["building_code"]) or id_by_name.get(r["building_code"])
        if not bid:
            # Could be a human-friendly building name in building_code field; try name
            bid = id_by_name.get(r["building_code"])
        if not bid:
            continue  # building not present; skip

        key = (bid, r["level_code"])
        if key in existing_pairs:
            continue

        conn.execute(
            insert_stmt,
            {"building_id": bid, "level_code": r["level_code"], "name": r["name"]},
        )
        existing_pairs.add(key)
        to_add += 1

    if to_add:
        conn.execute(text("COMMIT"))


def downgrade() -> None:
    conn = op.get_bind()
    csv_path = _resolve_csv_path("floors.csv", "floors_csv")
    if not csv_path or not csv_path.exists():
        return

    rows = _read_floors(csv_path)
    if not rows:
        return

    bld = conn.execute(text("SELECT id, code, name FROM buildings")).mappings().all()
    id_by_code = { (r["code"] or "").strip(): str(r["id"]) for r in bld if r.get("code") }
    id_by_name = { (r["name"] or "").strip(): str(r["id"]) for r in bld if r.get("name") }

    delete_stmt = text(
        "DELETE FROM floors WHERE building_id = :bid AND level_code = :lvl"
    )

    for r in rows:
        bid = id_by_code.get(r["building_code"]) or id_by_name.get(r["building_code"])
        if not bid:
            continue
        conn.execute(delete_stmt, {"bid": bid, "lvl": r["level_code"]})

    conn.execute(text("COMMIT"))