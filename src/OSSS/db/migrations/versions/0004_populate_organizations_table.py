"""seed organizations from CSV

Revision ID: 0004_populate_orgs_table
Revises: 0003_populate_states_table
Create Date: 2025-08-15 00:00:00
"""
from __future__ import annotations

import csv
from pathlib import Path

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0004_populate_orgs_table"
down_revision = "0003_populate_states_table"
branch_labels = None
depends_on = None


def _locate_csv() -> Path:
    """
    Look for organizations.csv either in the same directory as this migration
    or in a sibling 'data/' directory.
    """
    here = Path(__file__).resolve().parent
    direct = here / "organizations.csv"
    if direct.exists():
        return direct
    data_path = here / "data" / "organizations.csv"
    if data_path.exists():
        return data_path
    raise FileNotFoundError(
        f"organizations.csv not found at {direct} or {data_path}. "
        "Place the CSV next to this migration or in a 'data' subfolder."
    )


def _read_rows() -> list[dict[str, str]]:
    csv_path = _locate_csv()
    rows: list[dict[str, str]] = []
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        # Expect headers: code,name
        for r in reader:
            code = (r.get("code") or "").strip()
            name = (r.get("name") or "").strip()
            if not code or not name:
                continue
            rows.append({"code": code, "name": name})
    return rows


def upgrade() -> None:
    conn = op.get_bind()

    rows = _read_rows()
    if not rows:
        return

    # Upsert by code (organizations.code must be UNIQUE)
    upsert = sa.text(
        """
        INSERT INTO organizations (name, code)
        VALUES (:name, :code)
        ON CONFLICT (code) DO UPDATE
           SET name = EXCLUDED.name,
               updated_at = NOW()
        """
    )
    conn.execute(upsert, rows)


def downgrade() -> None:
    conn = op.get_bind()
    rows = _read_rows()
    if not rows:
        return

    # Delete by code; executemany for portability
    conn.execute(
        sa.text("DELETE FROM organizations WHERE code = :code"),
        [{"code": r["code"]} for r in rows],
    )
