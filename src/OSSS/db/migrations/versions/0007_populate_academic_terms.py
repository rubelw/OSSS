# versions/0007_populate_academic_terms.py
from __future__ import annotations

import csv
import os
from pathlib import Path
from datetime import date, datetime

from alembic import op, context
import sqlalchemy as sa

# --- Alembic identifiers ---
revision = "0007_populate_academic_terms"
down_revision = "0006_populate_behavior_codes"
branch_labels = None
depends_on = None


# ---------- helpers ----------
def _resolve_csv_path(filename_env: str, x_arg_key: str, default_filename: str) -> Path:
    """
    Resolve a CSV path in this order:
      1) -x <x_arg_key>=/path/to/file.csv
      2) ENV var <filename_env>
      3) <alembic script dir>/<default_filename>
    """
    x = context.get_x_argument(as_dictionary=True)
    if x.get(x_arg_key):
        return Path(x[x_arg_key]).expanduser().resolve()

    env_val = os.getenv(filename_env)
    if env_val:
        return Path(env_val).expanduser().resolve()

    # default to the directory of this migration file
    here = Path(__file__).resolve().parent
    return here / default_filename


def _load_terms(csv_path: Path) -> list[dict]:
    """Read rows from academic_terms.csv -> [{name, type, start_date, end_date}, ...]."""
    if not csv_path.exists():
        raise FileNotFoundError(f"academic terms CSV not found: {csv_path}")

    rows: list[dict] = []
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        required = {"name", "type", "start_date", "end_date"}
        if set(reader.fieldnames or []) != required and not required.issubset(set(reader.fieldnames or [])):
            raise ValueError(
                f"CSV must have headers: name,type,start_date,end_date (got {reader.fieldnames})"
            )

        for r in reader:
            # Expect ISO dates (YYYY-MM-DD)
            start_iso = r["start_date"].strip()
            end_iso = r["end_date"].strip()
            rows.append(
                {
                    "name": r["name"].strip(),
                    "type": r["type"].strip(),
                    "start_date": date.fromisoformat(start_iso),
                    "end_date": date.fromisoformat(end_iso),
                }
            )
    return rows


def _is_pg(bind) -> bool:
    return bind.dialect.name == "postgresql"


# ---------- migration ----------
def upgrade() -> None:
    bind = op.get_bind()

    # Optional: needed if you use gen_random_uuid() elsewhere in your project
    if _is_pg(bind):
        bind.execute(sa.text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))

    csv_path = _resolve_csv_path(
        filename_env="ACADEMIC_TERMS_CSV",
        x_arg_key="academic_terms_csv",
        default_filename="academic_terms.csv",
    )
    terms = _load_terms(csv_path)

    # Fetch all schools
    school_ids = [row[0] for row in bind.execute(sa.text("SELECT id FROM schools")).fetchall()]

    # Upsert behavior but without requiring a unique index:
    #  1) UPDATE existing rows (school_id, name) to keep data fresh
    #  2) INSERT rows that don't exist
    update_sql = sa.text(
        """
        UPDATE academic_terms
           SET type = :type,
               start_date = :start_date,
               end_date   = :end_date,
               updated_at = NOW()
         WHERE school_id = :school_id AND name = :name
        """
    )
    insert_sql = sa.text(
        """
        INSERT INTO academic_terms (school_id, name, type, start_date, end_date)
        SELECT :school_id, :name, :type, :start_date, :end_date
         WHERE NOT EXISTS (
               SELECT 1 FROM academic_terms
                WHERE school_id = :school_id AND name = :name
         )
        """
    )

    # executemany parameters
    update_params = []
    insert_params = []
    for sid in school_ids:
        for t in terms:
            base = {
                "school_id": str(sid),
                "name": t["name"],
                "type": t["type"],
                "start_date": t["start_date"],
                "end_date": t["end_date"],
            }
            update_params.append(base)
            insert_params.append(base)

    if update_params:
        bind.execute(update_sql, update_params)
    if insert_params:
        bind.execute(insert_sql, insert_params)


def downgrade() -> None:
    bind = op.get_bind()

    csv_path = _resolve_csv_path(
        filename_env="ACADEMIC_TERMS_CSV",
        x_arg_key="academic_terms_csv",
        default_filename="academic_terms.csv",
    )
    terms = _load_terms(csv_path)

    # delete only the rows this migration seeded, matched by (name, start_date, end_date)
    delete_sql = sa.text(
        """
        DELETE FROM academic_terms
         WHERE name = :name AND start_date = :start_date AND end_date = :end_date
        """
    )

    params = [{"name": t["name"], "start_date": t["start_date"], "end_date": t["end_date"]} for t in terms]
    if params:
        bind.execute(delete_sql, params)
