# versions/0034_populate_agenda_wkf.py
from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from alembic import op
import sqlalchemy as sa

revision = "0035_populate_folders"
down_revision = "0034_populate_agenda_wkf"
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
    here = Path(__file__).resolve().parent
    p = here / filename
    if p.exists():
        return p
    p = Path.cwd() / filename
    return p if p.exists() else None


def _as_bool(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    s = str(v or "").strip().lower()
    return s in {"1", "true", "t", "yes", "y", "on"}


def _read_csv(csv_path: Path) -> List[Dict[str, Any]]:
    """
    Expected header (case-sensitive):
      org_code,name,parent_name,is_public,sort_order

    - org_code: matches organizations.code (e.g., 05400000)
    - parent_name: optional; when present we link child to that parent
    - is_public: boolean-ish
    - sort_order: int-ish
    """
    rows: List[Dict[str, Any]] = []
    with csv_path.open(newline="", encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        req = {"org_code", "name"}
        if not req.issubset(set(rdr.fieldnames or [])):
            raise RuntimeError("folders.csv must include at least 'org_code' and 'name' columns")

        for r in rdr:
            org_code = (r.get("org_code") or "").strip()
            name = (r.get("name") or "").strip()
            if not org_code or not name:
                continue
            parent_name = (r.get("parent_name") or "").strip() or None
            is_public = _as_bool(r.get("is_public", False))
            so_raw = (r.get("sort_order") or "").strip()
            sort_order = int(so_raw) if so_raw.isdigit() else None

            rows.append(
                {
                    "org_code": org_code,
                    "name": name,
                    "parent_name": parent_name,
                    "is_public": is_public,
                    "sort_order": sort_order,
                }
            )
    return rows


# --------------------------
# migration
# --------------------------
def upgrade() -> None:
    bind = op.get_bind()  # Alembic manages the transaction for us
    csv_path = _resolve_csv_path("folders.csv", "folders_csv")
    if not csv_path:
        raise RuntimeError(
            "folders.csv not found. Place it next to this migration "
            "or pass -x folders_csv=/path/to/folders.csv"
        )

    rows = _read_csv(csv_path)
    if not rows:
        log.info("[0035_populate_folders] No rows found in %s; nothing to do.", csv_path)
        return

    # 1) Resolve org_code -> org_id (UUID) from organizations table
    codes = sorted({r["org_code"] for r in rows if r["org_code"]})
    org_map: Dict[str, Any] = {}
    if codes:
        res = bind.execute(
            sa.text("SELECT code, id FROM organizations WHERE code = ANY(:codes)"),
            {"codes": codes},
        ).mappings().all()
        org_map = {row["code"]: row["id"] for row in res}

    missing = [c for c in codes if c not in org_map]
    if missing:
        raise RuntimeError(f"[0035_populate_folders] Unknown organization codes in CSV: {missing}")

    # Prepared statements
    sel_folder = sa.text(
        "SELECT id, parent_id FROM folders WHERE org_id = :org_id AND name = :name LIMIT 1"
    )

    # Insert-if-not-exists pattern; RETURNING id works on PG, else we'll select again
    ins_folder = sa.text(
        """
        INSERT INTO folders (org_id, name, is_public, sort_order, parent_id)
        SELECT :org_id, :name, :is_public, :sort_order, :parent_id
        WHERE NOT EXISTS (
            SELECT 1 FROM folders WHERE org_id = :org_id AND name = :name
        )
        RETURNING id
        """
    )

    upd_folder = sa.text(
        """
        UPDATE folders
           SET parent_id = :parent_id,
               is_public = :is_public,
               sort_order = :sort_order
         WHERE id = :id
        """
    )

    # Cache to avoid redundant DB hits: (org_id, name) -> (id, parent_id)
    folder_cache: Dict[Tuple[Any, str], Tuple[Any, Any]] = {}

    def _get_or_create_folder(org_id: Any, name: str,
                              is_public: bool = False,
                              sort_order: Optional[int] = None,
                              parent_id: Optional[Any] = None) -> Any:
        key = (org_id, name)
        cached = folder_cache.get(key)
        if cached:
            return cached[0]

        row = bind.execute(sel_folder, {"org_id": org_id, "name": name}).mappings().first()
        if row:
            folder_cache[key] = (row["id"], row["parent_id"])
            return row["id"]

        # Try insert
        rid = None
        try:
            rid = bind.execute(
                ins_folder,
                {
                    "org_id": org_id,
                    "name": name,
                    "is_public": is_public,
                    "sort_order": sort_order,
                    "parent_id": parent_id,
                },
            ).scalar()
        except Exception:
            # fallback if dialect doesn't like RETURNING
            pass

        if not rid:
            # select again (either because insert didn't return, or it already existed)
            row2 = bind.execute(sel_folder, {"org_id": org_id, "name": name}).mappings().first()
            if not row2:
                raise RuntimeError(f"Failed to create/find folder: org_id={org_id} name={name}")
            rid = row2["id"]
            folder_cache[key] = (row2["id"], row2["parent_id"])
        else:
            folder_cache[key] = (rid, parent_id)

        return rid

    # 2) Ensure parents/children exist and are linked
    for r in rows:
        org_id = org_map[r["org_code"]]

        parent_id = None
        if r["parent_name"]:
            parent_id = _get_or_create_folder(org_id, r["parent_name"])

        child_id = _get_or_create_folder(
            org_id,
            r["name"],
            is_public=r["is_public"],
            sort_order=r["sort_order"],
            parent_id=parent_id,
        )

        # If existing child had different parent/is_public/sort_order, update it
        key = (org_id, r["name"])
        cached_id, cached_parent = folder_cache.get(key, (child_id, None))
        need_update = (
            cached_parent != parent_id
        )
        if need_update:
            bind.execute(
                upd_folder,
                {
                    "id": child_id,
                    "parent_id": parent_id,
                    "is_public": r["is_public"],
                    "sort_order": r["sort_order"],
                },
            )
            folder_cache[key] = (child_id, parent_id)

    log.info("[0035_populate_folders] Upserted/linked %d folder rows.", len(rows))


def downgrade() -> None:
    bind = op.get_bind()
    csv_path = _resolve_csv_path("folders.csv", "folders_csv")
    if not csv_path:
        log.info("[0035_populate_folders] No CSV found for downgrade; skipping delete.")
        return

    rows = _read_csv(csv_path)
    if not rows:
        return

    # group names by org_code to do targeted deletes
    by_org: Dict[str, List[str]] = {}
    for r in rows:
        by_org.setdefault(r["org_code"], []).append(r["name"])

    codes = sorted(by_org.keys())
    if not codes:
        return

    res = bind.execute(
        sa.text("SELECT code, id FROM organizations WHERE code = ANY(:codes)"),
        {"codes": codes},
    ).mappings().all()
    org_map = {row["code"]: row["id"] for row in res}

    for code, names in by_org.items():
        org_id = org_map.get(code)
        if not org_id:
            continue
        # Delete matching names for this org; parent/child will cascade via FK if configured
        bind.execute(
            sa.text("DELETE FROM folders WHERE org_id = :org_id AND name = ANY(:names)"),
            {"org_id": org_id, "names": names},
        )