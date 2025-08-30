# versions/0034_populate_agenda_wkf.py
from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from alembic import op
import sqlalchemy as sa

revision = "0034_populate_agenda_wkf"
down_revision = "0033_populate_asset_parts"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")


# --------------------------
# helpers
# --------------------------
def _get_x_arg(name: str, default: Optional[str] = None) -> Optional[str]:
    from alembic import context

    try:
        xargs = context.get_x_argument(as_dictionary=True)
    except Exception:
        return default
    return xargs.get(name, default)


def _resolve_csv_path(filename: str, xarg_key: str) -> Optional[Path]:
    override = _get_x_arg(xarg_key)
    if override:
        p = Path(override)
        return p if p.exists() else None
    # same folder as this migration file
    here = Path(__file__).resolve().parent
    p = here / filename
    if p.exists():
        return p
    # fallback to CWD
    p = Path.cwd() / filename
    return p if p.exists() else None


def _as_bool(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    s = str(v or "").strip().lower()
    return s in {"1", "true", "t", "yes", "y", "on"}


def _read_csv(csv_path: Path) -> List[Dict[str, Any]]:
    """
    Expected header:
      name, active
    """
    rows: List[Dict[str, Any]] = []
    with csv_path.open(newline="", encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        req = {"name"}
        if not req.issubset(set(rdr.fieldnames or [])):
            raise RuntimeError(
                "agenda_workflows.csv must include 'name' (and optional 'active') columns"
            )

        for r in rdr:
            name = (r.get("name") or "").strip()
            if not name:
                continue
            rows.append(
                {
                    "name": name,
                    "active": _as_bool(r.get("active", True)),
                }
            )
    return rows


# --------------------------
# migration
# --------------------------
def upgrade() -> None:
    bind = op.get_bind()  # already in a transaction under Alembic

    csv_path = _resolve_csv_path("agenda_workflows.csv", "agenda_workflows_csv")
    if not csv_path:
        raise RuntimeError(
            "agenda_workflows.csv not found. "
            "Place it next to this migration or pass -x agenda_workflows_csv=/path/to/agenda_workflows.csv"
        )

    rows = _read_csv(csv_path)
    if not rows:
        log.info("[0034_populate_agenda_wkf] No rows found in %s; nothing to do.", csv_path)
        return

    # Idempotent upsert behavior without requiring a unique constraint on name:
    # 1) Update existing rows by name
    upd_sql = sa.text("UPDATE agenda_workflows SET active = :active WHERE name = :name")

    # 2) Insert only if not exists
    ins_sql = sa.text(
        """
        INSERT INTO agenda_workflows (name, active)
        SELECT :name, :active
        WHERE NOT EXISTS (
            SELECT 1 FROM agenda_workflows WHERE name = :name
        )
        """
    )

    for r in rows:
        bind.execute(upd_sql, {"name": r["name"], "active": r["active"]})
        bind.execute(ins_sql, {"name": r["name"], "active": r["active"]})

    log.info("[0034_populate_agenda_wkf] Upserted %d workflows.", len(rows))


def downgrade() -> None:
    bind = op.get_bind()

    csv_path = _resolve_csv_path("agenda_workflows.csv", "agenda_workflows_csv")
    if not csv_path:
        log.info("[0034_populate_agenda_wkf] No CSV found for downgrade; skipping delete.")
        return

    rows = _read_csv(csv_path)
    names = [r["name"] for r in rows if r.get("name")]
    if not names:
        return

    # Simple loop keeps it backend-agnostic
    for name in names:
        bind.execute(sa.text("DELETE FROM agenda_workflows WHERE name = :name"), {"name": name})
