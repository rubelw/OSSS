from __future__ import annotations
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
import csv, os
from pathlib import Path

from datetime import datetime

# --- Alembic identifiers ---
revision = "0009_populate_attendance_codes"
down_revision = "0008_populate_standardized_tests"
branch_labels = None
depends_on = None

# Optional shims (left as-is if you rely on them elsewhere)
try:
    from app.models.base import GUID, JSONB, TSVectorType  # noqa: F401
except Exception:
    pass

# ----- helpers --------------------------------------------------------------

def _resolve_csv_path(
    default_name: str = "attendance_codes.csv",
    x_key: str = "attendance_codes_csv",
) -> str:
    """
    Resolve the CSV path by precedence:
      1) -x attendance_codes_csv=/abs/path.csv
      2) a file named `attendance_codes.csv` sitting next to this revision file
      3) current working directory fallback
    """
    # 1) allow -x override
    try:
        xargs = context.get_x_argument(as_dictionary=True)
        override = xargs.get(x_key)
    except Exception:
        override = None
    if override:
        return override
    here = os.path.dirname(__file__)
    candidate = os.path.join(here, default_name)
    if os.path.exists(candidate):
        return candidate
    return os.path.abspath(default_name)

def _parse_bool(v: str) -> bool:
    return str(v).strip().lower() in {"1", "true", "t", "yes", "y"}

# ----- upgrade / downgrade --------------------------------------------------

def upgrade() -> None:
    bind = op.get_bind()

    # Ensure table exists with a unique index/constraint on (code)
    # (If your schema already created this, the statements below are harmless.)
    # op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")  # if you depend on gen_random_uuid()
    # op.execute("""CREATE TABLE IF NOT EXISTS attendance_codes (
    #     code TEXT PRIMARY KEY,
    #     description TEXT NOT NULL,
    #     is_present BOOLEAN NOT NULL DEFAULT FALSE,
    #     is_excused BOOLEAN NOT NULL DEFAULT FALSE,
    #     created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    #     updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    # )""")

    csv_path = Path(_resolve_csv_path())

    if not csv_path.exists():
        raise FileNotFoundError(f"attendance codes CSV not found: {csv_path}")

    rows: list[dict] = []
    with csv_path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append({
                "code": r["code"].strip(),
                "description": r["description"].strip(),
                "is_present": _parse_bool(r["is_present"]),
                "is_excused": _parse_bool(r["is_excused"]),
                # If CSV has timestamps, use them; else let DB fill NOW()
                "created_at": r.get("created_at") or None,
                "updated_at": r.get("updated_at") or None,
            })

    # Upsert per code; keep created_at if present, always refresh updated_at
    # If your table has server defaults for created_at/updated_at,
    # we can omit them from INSERT to use defaults.
    is_pg = op.get_bind().dialect.name == "postgresql"
    ts_now = "NOW()" if is_pg else "CURRENT_TIMESTAMP"

    upsert = sa.text(f"""
        INSERT INTO attendance_codes
            (code, description, is_present, is_excused, created_at, updated_at)
        VALUES
            (:code, :description, :is_present, :is_excused, {ts_now}, {ts_now})
        ON CONFLICT (code) DO UPDATE
        SET description = EXCLUDED.description,
            is_present  = EXCLUDED.is_present,
            is_excused  = EXCLUDED.is_excused,
            updated_at  = {ts_now}
    """)

    # Execute in manageable batches
    for chunk_start in range(0, len(rows), 500):
        chunk = rows[chunk_start:chunk_start+500]
        bind.execute(upsert, chunk)

def downgrade() -> None:
    bind = op.get_bind()
    csv_path = _resolve_csv_path()
    if not csv_path.exists():
        # If the file is missing during downgrade, bail safely
        # or choose to no-op
        return

    codes: list[str] = []
    with csv_path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            codes.append(r["code"].strip())

    if not codes:
        return

    bind.execute(
        sa.text("DELETE FROM attendance_codes WHERE code = ANY(:codes)"),
        {"codes": codes},
    )
