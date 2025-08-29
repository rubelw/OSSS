from __future__ import annotations
from alembic import op
import sqlalchemy as sa
from pathlib import Path

from sqlalchemy import text
import os, csv, pathlib

# --- Alembic identifiers ---
revision = "0010_populate_roles"
down_revision = "0009_populate_attendance_codes"
branch_labels = None
depends_on = None

def _resolve_csv_path() -> Path:
    """
    Prefer (in order):
      1) alembic.ini main option 'roles_csv'
      2) env var ROLES_CSV
      3) roles.csv next to this revision file
    """
    ctx = op.get_context()
    cfg = getattr(ctx, "config", None)

    if cfg is not None:
        opt = cfg.get_main_option("roles_csv")
        if opt:
            return Path(opt).expanduser().resolve()

    if os.getenv("ROLES_CSV"):
        return Path(os.environ["ROLES_CSV"]).expanduser().resolve()

    return Path(__file__).with_name("roles.csv")

def _read_roles(csv_path: str) -> list[dict]:
    rows: list[dict] = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        # Expect headers: name, description
        for r in reader:
            name = (r.get("name") or "").strip()
            desc = (r.get("description") or "").strip()
            if not name:
                continue
            rows.append({"name": name, "description": desc})
    return rows

def upgrade() -> None:
    conn = op.get_bind()
    csv_path = _resolve_csv_path()
    roles = _read_roles(csv_path)

    if not roles:
        raise RuntimeError(f"No roles found in CSV at: {csv_path}")

    upsert = sa.text("""
        INSERT INTO roles (name, description)
        VALUES (:name, :description)
        ON CONFLICT (name) DO UPDATE
        SET description = EXCLUDED.description,
            updated_at = NOW()
    """)

    # execute many
    conn.execute(upsert, roles)

def downgrade() -> None:
    conn = op.get_bind()
    csv_path = _resolve_csv_path()
    roles = _read_roles(csv_path)
    if not roles:
        # Nothing to delete (safe no-op)
        return

    names = [r["name"] for r in roles if r.get("name")]
    # Use ANY(array) so it's one round-trip
    conn.execute(
        sa.text("DELETE FROM roles WHERE name = ANY(:names)"),
        {"names": names},
    )
