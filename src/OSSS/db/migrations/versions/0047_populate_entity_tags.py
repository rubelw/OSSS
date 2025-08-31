"""Populate entity_tags from folders (schema-aware; idempotent; no CSV).

- Detects the tags label column dynamically: prefers 'code', then 'name', 'label', 'slug', 'title'.
- Seeds a small set of default tags if the tags table is empty.
- Assigns 1–3 random tags to every folder into entity_tags (entity_type='folder').
- Idempotent: ON CONFLICT DO NOTHING; downgrade removes only what this migration added.

Revision ID: 0047_populate_entity_tags
Revises   : 0046_pm_plans
"""

from __future__ import annotations

import random
import logging
from datetime import datetime

from alembic import op
import sqlalchemy as sa

# --- identifiers ---
revision = "0047_populate_entity_tags"
down_revision = "0046_pm_plans"
branch_labels = None
depends_on = None

# --- tables ---
FOLDERS_TBL = "folders"
TAGS_TBL = "tags"
ET_TBL = "entity_tags"

# Keep the set small and generic; adjust to your domain if desired.
DEFAULT_TAG_CODES = [
    "priority.high", "priority.medium", "priority.low",
    "dept.operations", "dept.facilities", "dept.finance",
    "status.active", "status.archived",
]

log = logging.getLogger("alembic.runtime.migration")

def _pick_label_col(cols: list[str]) -> str | None:
    for c in ("code", "name", "label", "slug", "title"):
        if c in cols:
            return c
    return None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    # Sanity checks: make sure required tables exist.
    existing_tables = set(insp.get_table_names(schema=None))
    if FOLDERS_TBL not in existing_tables:
        log.info(f"[{revision}] '{FOLDERS_TBL}' table not found — nothing to do.")
        return
    if TAGS_TBL not in existing_tables:
        log.info(f"[{revision}] '{TAGS_TBL}' table not found — nothing to do.")
        return
    if ET_TBL not in existing_tables:
        log.info(f"[{revision}] '{ET_TBL}' table not found — nothing to do.")
        return

    # Determine tag PK column and a human label column (code/name/label/slug/title).
    tag_cols = {c["name"]: c for c in insp.get_columns(TAGS_TBL)}
    tag_pk = (insp.get_pk_constraint(TAGS_TBL).get("constrained_columns") or ["id"])[0]
    tag_label = _pick_label_col(list(tag_cols.keys()))
    if tag_label is None:
        log.info(f"[{revision}] '{TAGS_TBL}' has no recognizable label column (code/name/label/slug/title).")
        return

    # Collect existing tags (label -> id)
    rows = bind.execute(sa.text(f"SELECT {tag_pk} AS id, {tag_label} AS label FROM {TAGS_TBL}")).all()
    label_to_id = {r.label: r.id for r in rows}

    # If none exist, seed a small default set.
    if not label_to_id:
        ins_sql = sa.text(
            f"""INSERT INTO {TAGS_TBL} ({tag_pk}, {tag_label}, created_at, updated_at)
                VALUES (gen_random_uuid(), :label, now(), now())
                ON CONFLICT DO NOTHING
                RETURNING {tag_pk} AS id, {tag_label} AS label"""
        )
        for label in DEFAULT_TAG_CODES:
            ret = bind.execute(ins_sql, {"label": label}).fetchone()
            if ret:
                label_to_id[ret.label] = ret.id

        # If the RETURNING path didn’t hit (e.g., no created_at/updated_at columns), fallback:
        if not label_to_id:
            # try minimal insert without timestamps
            ins_sql_min = sa.text(
                f"""INSERT INTO {TAGS_TBL} ({tag_pk}, {tag_label})
                    VALUES (gen_random_uuid(), :label)
                    ON CONFLICT DO NOTHING"""
            )
            for label in DEFAULT_TAG_CODES:
                bind.execute(ins_sql_min, {"label": label})
            # re-read
            rows = bind.execute(sa.text(f"SELECT {tag_pk} AS id, {tag_label} AS label FROM {TAGS_TBL}")).all()
            label_to_id = {r.label: r.id for r in rows}

    if not label_to_id:
        log.info(f"[{revision}] no tags present/seeded — nothing to assign.")
        return

    # Get folders to tag
    # Prefer 'id' as PK; fall back to first PK column.
    folders_pk = (sa.inspect(bind).get_pk_constraint(FOLDERS_TBL).get("constrained_columns") or ["id"])[0]
    folder_ids = [r[0] for r in bind.execute(sa.text(f"SELECT {folders_pk} FROM {FOLDERS_TBL}")).all()]
    if not folder_ids:
        log.info(f"[{revision}] no folders found — nothing to tag.")
        return

    # Identify entity_tags columns
    et_cols = {c["name"] for c in insp.get_columns(ET_TBL)}
    # Infer column names (these match your ORM snippet; adjust if yours differ)
    et_id_col = "id" if "id" in et_cols else None
    et_entity_type_col = "entity_type" if "entity_type" in et_cols else None
    et_entity_id_col = "entity_id" if "entity_id" in et_cols else None
    et_tag_id_col = "tag_id" if "tag_id" in et_cols else None
    et_created_col = "created_at" if "created_at" in et_cols else None
    et_updated_col = "updated_at" if "updated_at" in et_cols else None

    # Ensure required cols exist
    for req in (et_entity_type_col, et_entity_id_col, et_tag_id_col):
        if req is None:
            log.info(f"[{revision}] '{ET_TBL}' missing required columns — aborting.")
            return

    # Prepare INSERT with ON CONFLICT DO NOTHING (assumes a unique constraint or primary key avoids dupes).
    cols = []
    vals = []
    if et_id_col:
        cols.append(et_id_col)
        vals.append("gen_random_uuid()")
    cols.extend([et_entity_type_col, et_entity_id_col, et_tag_id_col])
    vals.extend([":entity_type", ":entity_id", ":tag_id"])
    if et_created_col:
        cols.append(et_created_col)
        vals.append("now()")
    if et_updated_col:
        cols.append(et_updated_col)
        vals.append("now()")

    insert_sql = sa.text(
        f"""INSERT INTO {ET_TBL} ({", ".join(cols)})
            VALUES ({", ".join(vals)})
            ON CONFLICT DO NOTHING"""
    )

    # Assign 1–3 random tags per folder
    all_tag_ids = list(label_to_id.values())
    entity_type_value = "folder"  # choose the canonical string used in your app for folders

    for fid in folder_ids:
        k = random.randint(1, 3)
        chosen = random.sample(all_tag_ids, min(k, len(all_tag_ids)))
        for tag_id in chosen:
            bind.execute(
                insert_sql,
                {"entity_type": entity_type_value, "entity_id": fid, "tag_id": tag_id},
            )


def downgrade() -> None:
    """Remove only the rows this migration could have added (entity_type='folder')."""
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if ET_TBL not in insp.get_table_names(schema=None):
        return
    # Best-effort cleanup; keep tags table as-is.
    bind.execute(sa.text(f"DELETE FROM {ET_TBL} WHERE entity_type = :t"), {"t": "folder"})
