from __future__ import annotations

from alembic import op, context
import sqlalchemy as sa
from sqlalchemy import text
import csv, os
from pathlib import Path

# --- Alembic identifiers ---
revision = "0006_populate_behavior_codes"
down_revision = "0005_populate_schools_table"
branch_labels = None
depends_on = None

# Where to find the CSV:
#   Priority:
#     1) -x behavior_csv=/absolute/or/relative/path.csv
#     2) ENV BEHAVIOR_CODES_CSV
#     3) stateside default: ./behavior_codes.csv next to this migration file
def _resolve_csv_path() -> Path:
    xargs = context.get_x_argument(as_dictionary=True)
    if "behavior_csv" in xargs and xargs["behavior_csv"]:
        return Path(xargs["behavior_csv"]).expanduser().resolve()

    env = os.getenv("BEHAVIOR_CODES_CSV")
    if env:
        return Path(env).expanduser().resolve()

    # default next to this migration file
    here = Path(__file__).parent
    return (here / "behavior_codes.csv").resolve()

def _load_rows(csv_path: Path) -> list[dict[str, str]]:
    with csv_path.open("r", newline="", encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        rows: list[dict[str, str]] = []
        for i, row in enumerate(rdr, start=1):
            code = (row.get("code") or "").strip()
            desc = (row.get("description") or "").strip()
            if not code:
                # ignore empty / malformed lines
                continue
            rows.append({"code": code, "description": desc})
        return rows

def upgrade() -> None:
    conn = op.get_bind()

    csv_path = _resolve_csv_path()
    if not csv_path.exists():
        raise RuntimeError(
            f"[{revision}] behavior_codes.csv not found at: {csv_path}. "
            "Pass -x behavior_csv=/path/to/behavior_codes.csv or set BEHAVIOR_CODES_CSV."
        )

    rows = _load_rows(csv_path)
    if not rows:
        # Nothing to do; safe no-op
        return

    stmt = sa.text("""
        INSERT INTO behavior_codes (code, description)
        VALUES (:code, :description)
        ON CONFLICT (code) DO UPDATE
        SET description = EXCLUDED.description,
            updated_at  = NOW()
    """)

    # executemany
    conn.execute(stmt, rows)

def downgrade() -> None:
    conn = op.get_bind()

    csv_path = _resolve_csv_path()
    if not csv_path.exists():
        # Be forgiving on downgrade if CSV is missing
        return

    rows = _load_rows(csv_path)
    codes = [r["code"] for r in rows if r.get("code")]
    if not codes:
        return

    # Delete only those we seeded
    conn.execute(
        sa.text("DELETE FROM behavior_codes WHERE code = ANY(:codes)"),
        {"codes": codes},
    )
