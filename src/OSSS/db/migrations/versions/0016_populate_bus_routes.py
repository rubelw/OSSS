from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
import uuid
import csv
from pathlib import Path
from typing import Dict, List, Optional


# --- Alembic identifiers ---
revision = "0016_populate_bus_routes"
down_revision = "0015_populate_grading_periods"
branch_labels = None
depends_on = None


def _csv_path(filename_default: str = "bus_routes.csv") -> Path:
    """
    Resolve the CSV path. Supports:
      alembic upgrade head -x bus_routes_csv=/abs/or/relative/path.csv
    Falls back to file in the same directory as this migration,
    then to current working directory.
    """
    from alembic import context

    xargs = {k: v for k, v in (arg.split("=", 1) if "=" in arg else (arg, "") for arg in context.get_x_argument())}
    candidate = xargs.get("bus_routes_csv", filename_default)

    p = Path(candidate)
    if p.is_file():
        return p

    # Try alongside this migration file
    here = Path(__file__).resolve().parent
    p2 = here / filename_default
    if p2.is_file():
        return p2

    # Try CWD
    p3 = Path.cwd() / filename_default
    return p3


def _load_routes(csv_path: Path) -> List[Dict[str, Optional[str]]]:
    """
    Expect CSV headers: name, school_name
    """
    rows: List[Dict[str, Optional[str]]] = []
    if not csv_path.exists():
        return rows

    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            name = (r.get("name") or "").strip()
            school_name = (r.get("school_name") or "").strip()
            rows.append(
                {
                    "name": name,
                    "school_name": school_name or None,
                }
            )
    return rows


def _table(name: str, *cols: sa.Column) -> sa.Table:
    return sa.table(name, *cols)


def upgrade() -> None:
    bind = op.get_bind()

    csv_path = _csv_path()
    routes = _load_routes(csv_path)
    if not routes:
        # Nothing to insert if file missing/empty
        return

    # Map school name -> id
    school_rows = bind.execute(sa.text("SELECT id, name FROM schools")).mappings().all()
    school_by_name: Dict[str, str] = {r["name"]: r["id"] for r in school_rows}

    # Already-present route names (idempotency)
    existing_names = {
        r["name"] for r in bind.execute(sa.text("SELECT name FROM bus_routes")).mappings()
    }

    to_insert: List[Dict[str, Optional[str]]] = []
    for row in routes:
        route_name = row["name"]
        if not route_name or route_name in existing_names:
            continue
        school_name = row["school_name"]
        school_id = school_by_name.get(school_name) if school_name else None
        to_insert.append(
            {
                "id": str(uuid.uuid4()),
                "name": route_name,
                "school_id": school_id,
            }
        )

    if not to_insert:
        return

    bus_routes = _table(
        "bus_routes",
        sa.column("id", sa.String(36)),
        sa.column("name", sa.Text()),
        sa.column("school_id", sa.String(36)),
    )

    op.bulk_insert(bus_routes, to_insert)


def downgrade() -> None:
    bind = op.get_bind()

    csv_path = _csv_path()
    routes = _load_routes(csv_path)
    if not routes:
        return

    names = [r["name"] for r in routes if r.get("name")]

    # Cross-dialect friendly IN with expanding param
    stmt = sa.text("DELETE FROM bus_routes WHERE name IN :names").bindparams(
        sa.bindparam("names", expanding=True)
    )
    if names:
        bind.execute(stmt, {"names": names})
