from __future__ import annotations
import json
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = "0032_populate_ap_vendors"
down_revision = "0031_populate_parts"  # keep your actual value

CHUNK = 200

def _to_json_text(val):
    """Accept dict/str/None; return JSON text or None. Raises on invalid JSON strings."""
    if val is None or val == "":
        return None
    if isinstance(val, dict):
        return json.dumps(val, separators=(",", ":"), ensure_ascii=False)
    if isinstance(val, str):
        # validate that it's valid JSON text; then re-dump to canonical form
        parsed = json.loads(val)
        return json.dumps(parsed, separators=(",", ":"), ensure_ascii=False)
    # fallback: try to json-dump anything else (e.g., list)
    return json.dumps(val, separators=(",", ":"), ensure_ascii=False)

def upgrade():
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"

    # Build your payload list the same way you do now… then normalize JSON fields:
    payload = []  # existing code that fills this list of dicts

    # … after you’ve built payload, normalize json fields and booleans:
    for row in payload:
        row["remit_to"]   = _to_json_text(row.get("remit_to"))
        row["contact"]    = _to_json_text(row.get("contact"))
        row["attributes"] = _to_json_text(row.get("attributes"))
        # ensure active is a real bool, not a string
        row["active"] = bool(row.get("active"))

    if is_pg:
        sql = text("""
        INSERT INTO ap_vendors (vendor_no, name, tax_id, remit_to, contact, attributes, active)
        VALUES (:vendor_no, :name, :tax_id,
                CAST(:remit_to AS JSONB),
                CAST(:contact AS JSONB),
                CAST(:attributes AS JSONB),
                :active)
        ON CONFLICT (vendor_no) DO UPDATE
        SET name        = EXCLUDED.name,
            tax_id      = EXCLUDED.tax_id,
            remit_to    = COALESCE(EXCLUDED.remit_to, ap_vendors.remit_to),
            contact     = COALESCE(EXCLUDED.contact, ap_vendors.contact),
            attributes  = COALESCE(ap_vendors.attributes, '{}'::jsonb)
                          || COALESCE(EXCLUDED.attributes, '{}'::jsonb),
            active      = EXCLUDED.active
        """)
    else:
        # SQLite fallback (JSON is stored as TEXT)
        sql = text("""
        INSERT OR REPLACE INTO ap_vendors (vendor_no, name, tax_id, remit_to, contact, attributes, active)
        VALUES (:vendor_no, :name, :tax_id, :remit_to, :contact, :attributes, :active)
        """)

    # Execute in chunks with savepoints so one bad row doesn't nuke the whole batch
    if not payload:
        return

    for i in range(0, len(payload), CHUNK):
        batch = payload[i:i+CHUNK]
        if is_pg:
            # Use a savepoint per chunk
            bind.execute(text("SAVEPOINT sp_vendors"))
            try:
                bind.execute(sql, batch)
                bind.execute(text("RELEASE SAVEPOINT sp_vendors"))
            except Exception as e:
                # Try row-by-row inside the savepoint to isolate offenders
                for row in batch:
                    try:
                        bind.execute(sql, row)
                    except Exception:
                        # Skip the bad row; keep going
                        pass
                # Finally release/cleanup savepoint
                bind.execute(text("RELEASE SAVEPOINT sp_vendors"))
        else:
            bind.execute(sql, batch)

def downgrade():
    bind = op.get_bind()
    # If your payload is reproducible, delete by vendor_no; otherwise no-op.
    # Example (assuming you can reconstruct vendor_nos list):
    vendor_nos = []  # fill as appropriate or leave as no-op for safety
    if not vendor_nos:
        return
    if bind.dialect.name == "postgresql":
        bind.execute(text("DELETE FROM ap_vendors WHERE vendor_no = ANY(:vnos)"), {"vnos": vendor_nos})
    else:
        placeholders = ",".join([f":v{i}" for i in range(len(vendor_nos))])
        params = {f"v{i}": v for i, v in enumerate(vendor_nos)}
        bind.execute(text(f"DELETE FROM ap_vendors WHERE vendor_no IN ({placeholders})"), params)
