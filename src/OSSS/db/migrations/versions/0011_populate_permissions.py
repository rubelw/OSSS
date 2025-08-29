from alembic import op
import sqlalchemy as sa
import csv
import os

# --- Alembic identifiers ---
revision = "0011_populate_permissions"
down_revision = "0010_populate_roles"
branch_labels = None
depends_on = None


# ---------- file helpers ----------
def _csv_path(filename_env_key: str, default_filename: str) -> str:
    """
    Resolve a CSV path, preferring an Alembic -x var, then env var, then local file.
    Usage examples when running:
      alembic upgrade head -x permissions_csv=/data/permissions.csv -x permission_mappings_csv=/data/permission_mappings.csv
    """
    # Alembic context x-arguments
    from alembic import context
    x = (context.get_x_argument(as_dictionary=True) or {})
    if filename_env_key in x and x[filename_env_key]:
        return x[filename_env_key]

    # Environment variable fallback (e.g., PERMISSIONS_CSV, PERMISSION_MAPPINGS_CSV)
    env_key = filename_env_key.upper()
    if env_key in os.environ and os.environ[env_key]:
        return os.environ[env_key]

    # Local relative file
    return os.path.join(os.path.dirname(__file__), default_filename)


def _read_permissions(csv_path: str) -> list[dict]:
    out: list[dict] = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            code = (row.get("code") or "").strip()
            desc = (row.get("description") or "").strip()
            if not code:
                continue
            out.append({"code": code, "description": desc})
    return out


def _read_permission_mappings(csv_path: str) -> list[tuple[str, str]]:
    """
    Returns a list of (role_name, permission_code) pairs.
    CSV columns: role, permission_code
    """
    out: list[tuple[str, str]] = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            role = (row.get("role") or "").strip()
            pcode = (row.get("permission_code") or "").strip()
            if role and pcode:
                out.append((role, pcode))
    return out


def upgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"

    # Resolve CSVs
    permissions_csv = _csv_path("permissions_csv", "permissions.csv")
    mappings_csv = _csv_path("permission_mappings_csv", "permission_mappings.csv")

    permissions = _read_permissions(permissions_csv)
    role_perm_pairs = _read_permission_mappings(mappings_csv)

    # 1) Upsert permissions
    if is_pg:
        insert_perm = sa.text("""
            INSERT INTO permissions (code, description)
            VALUES (:code, :desc)
            ON CONFLICT (code) DO UPDATE
            SET description = EXCLUDED.description
        """)
    else:
        insert_perm = sa.text("""
            INSERT OR IGNORE INTO permissions (code, description)
            VALUES (:code, :desc)
        """)
        update_desc = sa.text("UPDATE permissions SET description = :desc WHERE code = :code")

    for p in permissions:
        bind.execute(insert_perm, {"code": p["code"], "desc": p["description"]})
        if not is_pg:
            bind.execute(update_desc, {"code": p["code"], "desc": p["description"]})

    # Build permission_id map
    perm_codes = [p["code"] for p in permissions]
    sel_perms = (
        sa.text("SELECT id, code FROM permissions WHERE code = ANY(:codes)")
        if is_pg else sa.text("SELECT id, code FROM permissions")
    )
    perm_rows = bind.execute(sel_perms, {"codes": perm_codes} if is_pg else {}).mappings().all()
    perm_id_by_code = {r["code"]: r["id"] for r in perm_rows if r["code"] in perm_codes}

    # Build role_id map (roles should already be seeded)
    role_names = sorted({rp[0] for rp in role_perm_pairs})
    sel_roles = (
        sa.text("SELECT id, name FROM roles WHERE name = ANY(:names)")
        if is_pg else sa.text("SELECT id, name FROM roles")
    )
    role_rows = bind.execute(sel_roles, {"names": role_names} if is_pg else {}).mappings().all()
    role_id_by_name = {r["name"]: r["id"] for r in role_rows if r["name"] in role_names}

    # 2) Link roles to permissions
    if is_pg:
        insert_rp = sa.text("""
            INSERT INTO role_permissions (role_id, permission_id, created_at, updated_at)
            VALUES (:rid, :pid, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT DO NOTHING
        """)
    else:
        insert_rp = sa.text("""
            INSERT OR IGNORE INTO role_permissions (role_id, permission_id, created_at, updated_at)
            VALUES (:rid, :pid, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """)

    for role_name, perm_code in role_perm_pairs:
        rid = role_id_by_name.get(role_name)
        pid = perm_id_by_code.get(perm_code)
        if rid and pid:
            bind.execute(insert_rp, {"rid": rid, "pid": pid})
        # silently skip unknown roles or permissions

def downgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"

    # Re-read the same CSV to know which permission codes we added
    permissions_csv = _csv_path("permissions_csv", "permissions.csv")
    permissions = _read_permissions(permissions_csv)
    perm_codes = [p["code"] for p in permissions]

    # 1) Remove role_permission links for these permissions
    if is_pg:
        sel_perm_ids = sa.text("SELECT id FROM permissions WHERE code = ANY(:codes)")
        perm_ids = [r["id"] for r in bind.execute(sel_perm_ids, {"codes": perm_codes}).mappings().all()]
        if perm_ids:
            bind.execute(sa.text("DELETE FROM role_permissions WHERE permission_id = ANY(:pids)"),
                         {"pids": perm_ids})
        # 2) Delete permissions
        bind.execute(sa.text("DELETE FROM permissions WHERE code = ANY(:codes)"), {"codes": perm_codes})
    else:
        # SQLite
        qmarks = ",".join(["?"] * len(perm_codes)) if perm_codes else "''"
        # Remove links first
        sel_perm_ids = sa.text(f"SELECT id FROM permissions WHERE code IN ({qmarks})")
        perm_ids = [r[0] for r in bind.execute(sel_perm_ids, perm_codes).fetchall()]
        if perm_ids:
            qmarks_ids = ",".join(["?"] * len(perm_ids))
            bind.execute(sa.text(f"DELETE FROM role_permissions WHERE permission_id IN ({qmarks_ids})"), perm_ids)
        # Delete permissions
        bind.execute(sa.text(f"DELETE FROM permissions WHERE code IN ({qmarks})"), perm_codes)
