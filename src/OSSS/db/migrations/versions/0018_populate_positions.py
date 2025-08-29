# alembic revision: add initial HR positions (CSV-driven)
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import text
import csv, os

# --- Alembic identifiers ---
revision = "0018_populate_positions"
down_revision = "0016_populate_bus_routes"
branch_labels = None
depends_on = None


def _alembic_x_arg(key: str) -> str | None:
    """
    Allow passing file paths at runtime:
      alembic upgrade head -x positions_csv=/abs/path/positions.csv -x position_accronyms_csv=/abs/path/position_accronyms.csv
    """
    try:
        from alembic import context
        x = context.get_x_argument(as_dictionary=True)
        return x.get(key)
    except Exception:
        return None


def _csv_path(default_name: str, x_key: str) -> str:
    # 1) explicit -x override, 2) same dir as migration, 3) current CWD fallback
    override = _alembic_x_arg(x_key)
    if override:
        return override
    here = os.path.dirname(__file__)
    p = os.path.join(here, default_name)
    if os.path.exists(p):
        return p
    return os.path.abspath(default_name)


def _load_positions_csv(path: str) -> list[str]:
    slugs: list[str] = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if "slug" not in (reader.fieldnames or []):
            raise RuntimeError(f"{path} must have a header 'slug'")
        for row in reader:
            s = row.get("slug")
            if s:
                slugs.append(s.strip())
    return slugs


def _load_acronyms_csv(path: str) -> dict[str, str]:
    """
    Load search/replace pairs. We intentionally DO NOT strip() values,
    so trailing spaces in the CSV are preserved for exact replacements.
    """
    fixes: dict[str, str] = {}
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if not {"search", "replace"}.issubset(set(reader.fieldnames or [])):
            raise RuntimeError(f"{path} must have headers 'search' and 'replace'")
        for row in reader:
            k = row.get("search")
            v = row.get("replace")
            if k is None or v is None:
                continue
            fixes[k] = v
    return fixes


def _slug_to_title(slug: str, fixes: dict[str, str]) -> str:
    """
    Convert a snake_case slug to a display title, then apply CSV-driven fixes.
    Example: 'chief_financial_officer' -> 'Chief Financial Officer' -> 'CFO' (via fix)
    """
    base = slug.replace("_", " ").title()
    title = base
    for search, replace in fixes.items():
        title = title.replace(search, replace)
    return title


def upgrade() -> None:
    conn = op.get_bind()

    # Resolve CSV paths (defaults to files next to this migration)
    positions_csv = _csv_path("positions.csv", "positions_csv")
    acronyms_csv = _csv_path("position_accronyms.csv", "position_accronyms_csv")

    slugs = _load_positions_csv(positions_csv)
    fixes = _load_acronyms_csv(acronyms_csv)

    hr_positions = sa.table(
        "hr_positions",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("title", sa.String()),
        sa.column("department_segment_id", postgresql.UUID(as_uuid=True)),
        sa.column("grade", sa.String()),
        sa.column("fte", sa.Numeric(5, 2)),
        sa.column("attributes", postgresql.JSONB),
    )

    # Gather existing slugs (preferred) and titles to avoid duplicates
    try:
        existing_slugs = set(
            r[0]
            for r in conn.execute(
                sa.text(
                    "SELECT attributes->>'slug' AS slug FROM hr_positions WHERE attributes ? 'slug'"
                )
            )
            if r[0] is not None
        )
    except Exception:
        existing_slugs = set()

    existing_titles = set(
        r[0] for r in conn.execute(sa.text("SELECT title FROM hr_positions"))
    )

    rows_to_insert = []
    for slug in slugs:
        title = _slug_to_title(slug, fixes)
        if slug in existing_slugs or title in existing_titles:
            continue
        rows_to_insert.append(
            {
                "title": title,
                "department_segment_id": None,
                "grade": None,
                "fte": None,
                "attributes": {"slug": slug},
            }
        )

    if rows_to_insert:
        op.bulk_insert(hr_positions, rows_to_insert)


def downgrade() -> None:
    conn = op.get_bind()

    positions_csv = _csv_path("positions.csv", "positions_csv")
    slugs = _load_positions_csv(positions_csv)

    # Prefer deleting by slug in attributes; fallback to title matches
    # We need fixes to compute titles for fallback.
    acronyms_csv = _csv_path("position_accronyms.csv", "position_accronyms_csv")
    fixes = _load_acronyms_csv(acronyms_csv)

    titles = [_slug_to_title(s, fixes) for s in slugs]

    conn.execute(
        sa.text(
            """
            DELETE FROM hr_positions
            WHERE (attributes ? 'slug' AND attributes->>'slug' = ANY(:slugs))
               OR title = ANY(:titles)
            """
        ),
        {"slugs": slugs, "titles": titles},
    )
