from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
import csv
from pathlib import Path

# --- Alembic identifiers ---
revision = "0012_populate_departments"
down_revision = "0011_populate_permissions"
branch_labels = None
depends_on = None


def _get_x_arg(name: str, default: str | None = None) -> str | None:
    """Read a -x key=value argument passed to Alembic."""
    from alembic import context
    xargs = context.get_x_argument(as_dictionary=True)
    return xargs.get(name, default)


def _resolve_csv_path(filename: str, xarg_key: str) -> Path | None:
    """Resolve a CSV path from -x arg, the migration's folder, or CWD."""
    override = _get_x_arg(xarg_key)
    if override:
        p = Path(override).expanduser().resolve()
        return p if p.exists() else None

    # look next to this migration file
    here = Path(__file__).resolve().parent
    p = here / filename
    if p.exists():
        return p

    # fallback: current working directory
    p = Path.cwd() / filename
    return p if p.exists() else None


def _read_departments(csv_path: Path) -> list[str]:
    """Expect a CSV with header 'name'."""
    names: list[str] = []
    with csv_path.open(newline="", encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        if "name" not in (rdr.fieldnames or []):
            raise RuntimeError("departments.csv must contain a 'name' column")
        for row in rdr:
            name = (row.get("name") or "").strip()
            if name:
                names.append(name)
    return names


def _read_schools(csv_path: Path) -> list[dict]:
    """
    Expect schools.csv with at least:
      - name
      - building_code  (used as school_code in DB)
    Optionally nces_school_id, etc. Extra columns ignored.
    """
    out: list[dict] = []
    with csv_path.open(newline="", encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        required = {"name", "building_code"}
        if not required.issubset(set(rdr.fieldnames or [])):
            raise RuntimeError("schools.csv must have columns: name, building_code")
        for row in rdr:
            out.append(
                {
                    "name": (row.get("name") or "").strip(),
                    "school_code": (row.get("building_code") or "").strip(),
                }
            )
    return out


def _fetch_target_school_ids(conn, school_rows_from_csv: list[dict]) -> list[str]:
    """
    Resolve DB school ids by (school_code or name) from CSV rows.
    Returns list of UUIDs (as strings).
    """
    codes = [r["school_code"] for r in school_rows_from_csv if r.get("school_code")]
    names = [r["name"] for r in school_rows_from_csv if r.get("name")]

    stmt = sa.text(
        """
        SELECT id, name, school_code
        FROM schools
        WHERE (COALESCE(school_code,'') <> '' AND school_code = ANY(:codes))
           OR name = ANY(:names)
        """
    )
    rows = conn.execute(stmt, {"codes": codes, "names": names}).mappings().all()
    # Build lookup maps
    by_code = {r["school_code"]: r["id"] for r in rows if r.get("school_code")}
    by_name = {r["name"]: r["id"] for r in rows}

    ids: list[str] = []
    for r in school_rows_from_csv:
        sid = by_code.get(r.get("school_code")) or by_name.get(r.get("name"))
        if sid:
            ids.append(str(sid))
    return ids


def upgrade() -> None:
    conn = op.get_bind()

    # Resolve CSV paths
    departments_csv = _resolve_csv_path("departments.csv", "departments_csv")
    schools_csv = _resolve_csv_path("schools.csv", "schools_csv")

    if not departments_csv or not departments_csv.exists():
        raise RuntimeError("departments.csv not found. Pass -x departments_csv=/path/to/departments.csv")
    if not schools_csv or not schools_csv.exists():
        raise RuntimeError("schools.csv not found. Pass -x schools_csv=/path/to/schools.csv")

    dept_names = _read_departments(departments_csv)
    school_rows = _read_schools(schools_csv)

    school_ids = _fetch_target_school_ids(conn, school_rows)
    if not school_ids:
        # Nothing to do (keeps migration idempotent on empty/partial DBs)
        return

    if conn.dialect.name == "postgresql":
        # Use NOT EXISTS so we don't need a unique constraint on (school_id, name)
        insert_stmt = sa.text(
            """
            INSERT INTO departments (school_id, name)
            SELECT :school_id, :name
            WHERE NOT EXISTS (
              SELECT 1 FROM departments d
              WHERE d.school_id = :school_id AND d.name = :name
            )
            """
        )
    else:
        # SQLite-friendly "INSERT OR IGNORE"
        insert_stmt = sa.text(
            "INSERT OR IGNORE INTO departments (school_id, name) VALUES (:school_id, :name)"
        )

    for sid in school_ids:
        for dname in dept_names:
            conn.execute(insert_stmt, {"school_id": sid, "name": dname})


def downgrade() -> None:
    conn = op.get_bind()

    # Resolve CSV paths again to know which rows to remove
    departments_csv = _resolve_csv_path("departments.csv", "departments_csv")
    schools_csv = _resolve_csv_path("schools.csv", "schools_csv")
    if not departments_csv or not schools_csv or not departments_csv.exists() or not schools_csv.exists():
        # If CSVs aren’t available, do nothing rather than risking deleting user data.
        return

    dept_names = _read_departments(departments_csv)
    school_rows = _read_schools(schools_csv)
    school_ids = _fetch_target_school_ids(conn, school_rows)
    if not school_ids or not dept_names:
        return

    delete_stmt = sa.text(
        """
        DELETE FROM departments
        WHERE school_id = ANY(:sids) AND name = ANY(:names)
        """
    ) if conn.dialect.name == "postgresql" else sa.text(
        "DELETE FROM departments WHERE school_id IN (%s) AND name IN (%s)" % (
            ",".join([":sid_%d" % i for i in range(len(school_ids))]),
            ",".join([":nm_%d" % i for i in range(len(dept_names))]),
        )
    )

    if conn.dialect.name == "postgresql":
        conn.execute(delete_stmt, {"sids": school_ids, "names": dept_names})
    else:
        params = {f"sid_{i}": v for i, v in enumerate(school_ids)}
        params.update({f"nm_{i}": v for i, v in enumerate(dept_names)})
        conn.execute(delete_stmt, params)
