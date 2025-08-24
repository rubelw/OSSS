from alembic import op
import sqlalchemy as sa

# --- Alembic identifiers ---
revision = "0005_populate_schools_table"
down_revision = "0004_populate_orgs_table"
branch_labels = None
depends_on = None

# Dallas Center–Grimes schools data (TEXT everywhere)
SCHOOLS: list[tuple[str, str, str]] = [
    ("Dallas Center Elementary",           "190852000705", "436"),
    ("Dallas Center-Grimes High School",   "190852000451", "109"),
    ("Dallas Center-Grimes Middle School", "190852000453", "209"),
    ("DC-G Oak View",                      "190852002174", "218"),
    ("Heritage Elementary",                "190852002242", "437"),
    ("North Ridge Elementary",             "190852002099", "418"),
    ("South Prairie Elementary",           "190852002029", "427"),
]

# Official district code for Dallas Center–Grimes
DCG_CODE = "15760000"

def _log(msg: str) -> None:
    print(f"[0007] {msg}")

def _find_dcg_organization_id(conn) -> str | None:
    # 1) Try code (most reliable)
    did = conn.scalar(sa.text("SELECT id FROM organizations WHERE code = :c"), {"c": DCG_CODE})
    if did:
        _log(f"Matched organization by code={DCG_CODE} -> {did}")
        return did

    # 2) Try several name variants
    exact_candidates = [
        "Dallas Center-Grimes",
        "Dallas Center–Grimes",  # en dash
        "Dallas Center Grimes",
        "Dallas Center-Grimes Community School District",
        "Dallas Center–Grimes Community School District",
    ]
    for cand in exact_candidates:
        did = conn.scalar(sa.text("SELECT id FROM organizations WHERE name = :n"), {"n": cand})
        if did:
            _log(f"Matched organization by exact name '{cand}' -> {did}")
            return did

    # 3) Fallback fuzzy
    did = conn.scalar(
        sa.text(
            "SELECT id FROM organizations "
            "WHERE name ILIKE '%Dallas Center%' AND name ILIKE '%Grimes%' "
            "ORDER BY LENGTH(name) ASC LIMIT 1"
        )
    )
    if did:
        _log(f"Matched organization by fuzzy ILIKE -> {did}")
    else:
        _log("Organization lookup failed (Dallas Center–Grimes not found).")
    return did

def upgrade():
    conn = op.get_bind()

    # Ensure gen_random_uuid() exists (pgcrypto)
    conn.execute(sa.text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))

    # Ensure columns exist (idempotent on PostgreSQL)
    conn.execute(sa.text("ALTER TABLE schools ADD COLUMN IF NOT EXISTS nces_school_id TEXT"))
    conn.execute(sa.text("ALTER TABLE schools ADD COLUMN IF NOT EXISTS building_code  TEXT"))
    _log("Ensured columns nces_school_id, building_code exist on schools.")

    # Resolve organization id (by code first)
    organization_id = _find_dcg_organization_id(conn)
    if not organization_id:
        raise RuntimeError(
            "Organization for Dallas Center–Grimes not found. "
            "Verify 0006_populate_districts_table inserted code=15760000 or a compatible name."
        )

    sel_id_sql = sa.text("SELECT id FROM schools WHERE organization_id = :d AND name = :n")
    upd_sql = sa.text(
        "UPDATE schools "
        "   SET nces_school_id = :nces, "
        "       building_code  = :bcode, "
        "       school_code    = COALESCE(school_code, :bcode), "
        "       updated_at     = NOW() "
        " WHERE id = :id"
    )
    ins_sql = sa.text(
        "INSERT INTO schools "
        "    (id, organization_id, name, nces_school_id, building_code, school_code, created_at, updated_at) "
        "VALUES (gen_random_uuid(), :d, :n, :nces, :bcode, :bcode, NOW(), NOW())"
    )

    inserted = updated = 0
    for name, nces, bcode in SCHOOLS:
        existing_id = conn.scalar(sel_id_sql, {"d": organization_id, "n": name})
        if existing_id:
            conn.execute(upd_sql, {"id": existing_id, "nces": nces, "bcode": bcode})
            updated += 1
            _log(f"Updated: {name} (id={existing_id}) nces={nces} bcode={bcode}")
        else:
            conn.execute(ins_sql, {"d": organization_id, "n": name, "nces": nces, "bcode": bcode})
            inserted += 1
            _log(f"Inserted: {name} nces={nces} bcode={bcode}")

    # Post-check: count & sample rows we just touched
    count = conn.scalar(sa.text("SELECT COUNT(*) FROM schools WHERE organization_id = :d"), {"d": organization_id})
    sample = conn.execute(
        sa.text(
            "SELECT name, nces_school_id, building_code "
            "FROM schools WHERE organization_id = :d ORDER BY name LIMIT 10"
        ),
        {"d": organization_id},
    ).fetchall()

    _log(f"Done. Inserted={inserted}, Updated={updated}, OrganizationRowCount={count}")
    _log(f"Sample rows: {sample}")

def downgrade():
    conn = op.get_bind()
    organization_id = _find_dcg_organization_id(conn)
    if not organization_id:
        _log("Downgrade: DCG organization not found; skipping.")
        return

    # Clear only the fields we populated
    upd_null_sql = sa.text(
        "UPDATE schools "
        "   SET nces_school_id = NULL, building_code = NULL, updated_at = NOW() "
        " WHERE organization_id = :d AND name = :n"
    )
    for name, _, _ in SCHOOLS:
        conn.execute(upd_null_sql, {"d": organization_id, "n": name})
        _log(f"Cleared fields on: {name}")
