# versions/0032_populate_ap_vendors.py
from __future__ import annotations

import csv
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from alembic import op
import sqlalchemy as sa

revision = "0032_populate_ap_vendors"
down_revision = "0032_populate_asset_parts"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")


# --------------------------
# helpers
# --------------------------
def as_bool(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    s = str(v or "").strip().lower()
    return s in {"1", "true", "t", "yes", "y", "on"}


def as_json(v: Any) -> Optional[Dict[str, Any]]:
    """Parse CSV cell to a JSON(dict) value or None."""
    if v is None or v == "":
        return None
    if isinstance(v, (dict, list)):
        # normalize lists if they appear; wrap to keep column as dict
        return v if isinstance(v, dict) else {"value": v}  # type: ignore[return-value]
    try:
        parsed = json.loads(v)
        return parsed if isinstance(parsed, dict) else {"value": parsed}
    except Exception:
        # last resort: wrap raw text so it’s valid JSON
        return {"raw": str(v)}


def _get_x_arg(name: str, default: Optional[str] = None) -> Optional[str]:
    from alembic import context
    try:
        xargs = context.get_x_argument(as_dictionary=True)
    except Exception:
        return default
    return xargs.get(name, default)


def _resolve_csv_path(filename: str, xarg_key: str) -> Optional[Path]:
    override = _get_x_arg(xarg_key)
    if override:
        p = Path(override)
        return p if p.exists() else None
    # same folder as this migration file
    here = Path(__file__).resolve().parent
    p = here / filename
    if p.exists():
        return p
    # fallback to CWD
    p = Path.cwd() / filename
    return p if p.exists() else None


def _read_csv(csv_path: Path) -> List[Dict[str, Any]]:
    """
    Expected header:
      vendor_no, name, tax_id, remit_to, contact, attributes, active
    JSON fields should be JSON strings.
    """
    rows: List[Dict[str, Any]] = []
    with csv_path.open(newline="", encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        req = {"vendor_no", "name"}
        if not req.issubset(set(rdr.fieldnames or [])):
            raise RuntimeError("ap_vendors.csv must include at least 'vendor_no' and 'name' columns")

        for r in rdr:
            vendor_no = (r.get("vendor_no") or "").strip()
            name = (r.get("name") or "").strip()
            if not vendor_no or not name:
                continue

            rows.append(
                {
                    "vendor_no": vendor_no,
                    "name": name,
                    "tax_id": (r.get("tax_id") or "").strip() or None,
                    "remit_to": as_json(r.get("remit_to")),
                    "contact": as_json(r.get("contact")),
                    "attributes": as_json(r.get("attributes")),
                    "active": as_bool(r.get("active", True)),
                }
            )
    return rows


# --------------------------
# migration
# --------------------------
def upgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"

    csv_path = _resolve_csv_path("ap_vendors.csv", "ap_vendors_csv")
    if not csv_path:
        raise RuntimeError("ap_vendors.csv not found. Pass -x ap_vendors_csv=/path/to/ap_vendors.csv")

    rows = _read_csv(csv_path)
    if not rows:
        log.info("[0032_populate_ap_vendors] No rows found in %s; nothing to do.", csv_path)
        return

    # Detect optional vendor_id column in ap_vendors (FK to vendors.id) for linking
    inspector = sa.inspect(bind)
    ap_cols = {c["name"] for c in inspector.get_columns("ap_vendors")}
    has_vendor_fk = "vendor_id" in ap_cols

    # Build lookup from vendors by attributes->>'vendor_no' and by name (case-insensitive)
    vendor_map_by_no: Dict[str, str] = {}
    vendor_map_by_name: Dict[str, str] = {}
    try:
        vendor_rows = bind.execute(
            sa.text("SELECT id, name, attributes->>'vendor_no' AS vendor_no FROM vendors")
        ).mappings().all()
        vendor_map_by_no = {(r["vendor_no"] or "").strip(): r["id"] for r in vendor_rows if r["vendor_no"]}
        vendor_map_by_name = {(r["name"] or "").lower(): r["id"] for r in vendor_rows if r["name"]}
    except Exception:
        # vendors table may not exist in some installs; proceed without linking
        pass

    # Prepare upsert into ap_vendors
    cols = ["vendor_no", "name", "tax_id", "remit_to", "contact", "attributes", "active"]
    if has_vendor_fk:
        cols.append("vendor_id")

    placeholders = ", ".join(f":{c}" for c in cols)
    col_list = ", ".join(cols)

    if is_pg:
        on_conflict = """
            ON CONFLICT (vendor_no) DO UPDATE
            SET name        = EXCLUDED.name,
                tax_id      = EXCLUDED.tax_id,
                remit_to    = COALESCE(EXCLUDED.remit_to, ap_vendors.remit_to),
                contact     = COALESCE(EXCLUDED.contact, ap_vendors.contact),
                attributes  = COALESCE(ap_vendors.attributes, '{}'::jsonb)
                              || COALESCE(EXCLUDED.attributes, '{}'::jsonb),
                active      = EXCLUDED.active
        """
    else:
        # Non-Postgres backends: do plain insert; we’ll emulate upsert below if needed
        on_conflict = ""

    txt = f"""
        INSERT INTO ap_vendors ({col_list})
        VALUES ({placeholders})
        {on_conflict}
    """

    # Bind JSON/JSONB types explicitly so VALUES don't need ::json/jsonb casts
    json_type = sa.dialects.postgresql.JSONB if is_pg else sa.JSON
    bp = [
        sa.bindparam("vendor_no"),
        sa.bindparam("name"),
        sa.bindparam("tax_id"),
        sa.bindparam("remit_to", type_=json_type),
        sa.bindparam("contact", type_=json_type),
        sa.bindparam("attributes", type_=json_type),
        sa.bindparam("active"),
    ]
    if has_vendor_fk:
        bp.append(sa.bindparam("vendor_id"))

    sql = sa.text(txt).bindparams(*bp)

    payload: List[Dict[str, Any]] = []
    for r in rows:
        vendor_id: Optional[str] = None
        # Prefer lookup by vendor_no in vendors.attributes
        vendor_id = vendor_map_by_no.get(r["vendor_no"])
        # Fall back to case-insensitive name match
        if not vendor_id:
            vendor_id = vendor_map_by_name.get(r["name"].lower())
            # If we found by name but vendors has no vendor_no yet, backfill it (Postgres only)
            if vendor_id and is_pg:
                bind.execute(
                    sa.text("""
                        UPDATE vendors
                           SET attributes = COALESCE(attributes, '{}'::jsonb)
                                            || jsonb_build_object('vendor_no', :vendor_no)
                         WHERE id = :vid
                           AND (attributes->>'vendor_no') IS NULL
                    """),
                    {"vendor_no": r["vendor_no"], "vid": vendor_id},
                )

        item = {
            "vendor_no": r["vendor_no"],
            "name": r["name"],
            "tax_id": r["tax_id"],
            "remit_to": r["remit_to"],
            "contact": r["contact"],
            "attributes": r["attributes"],
            "active": r["active"],
        }
        if has_vendor_fk:
            item["vendor_id"] = vendor_id
        payload.append(item)

    # Execute in chunks (and emulate upsert for non-PG)
    CHUNK = 200
    if is_pg:
        for i in range(0, len(payload), CHUNK):
            bind.execute(sql, payload[i : i + CHUNK])
        log.info("[0032_populate_ap_vendors] Upserted %d vendors (Postgres).", len(payload))
    else:
        meta = sa.MetaData()
        vendors_tbl = sa.Table("ap_vendors", meta, autoload_with=bind)
        with bind.begin() as conn:
            for row in payload:
                exists = conn.execute(
                    sa.select(vendors_tbl.c.vendor_no).where(vendors_tbl.c.vendor_no == row["vendor_no"])
                ).first()
                if exists:
                    upd_vals = {k: row[k] for k in row.keys() if k != "vendor_no"}
                    conn.execute(
                        vendors_tbl.update().where(vendors_tbl.c.vendor_no == row["vendor_no"]).values(**upd_vals)
                    )
                else:
                    conn.execute(vendors_tbl.insert().values(**row))
        log.info("[0032_populate_ap_vendors] Upserted %d vendors (generic backend).", len(payload))


def downgrade() -> None:
    bind = op.get_bind()
    csv_path = _resolve_csv_path("ap_vendors.csv", "ap_vendors_csv")
    if not csv_path:
        # If we don't have the CSV to know which rows to remove, do nothing
        log.info("[0032_populate_ap_vendors] No CSV found for downgrade; skipping delete.")
        return

    rows = _read_csv(csv_path)
    vendor_nos = [r["vendor_no"] for r in rows]

    if not vendor_nos:
        return

    if bind.dialect.name == "postgresql":
        bind.execute(sa.text("DELETE FROM ap_vendors WHERE vendor_no = ANY(:nos)"), {"nos": vendor_nos})
    else:
        # generic fallback
        for vno in vendor_nos:
            bind.execute(sa.text("DELETE FROM ap_vendors WHERE vendor_no = :vno"), {"vno": vno})
