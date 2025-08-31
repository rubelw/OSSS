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
from pathlib import Path
import os
import json
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg
import csv
import json

# --- identifiers ---
revision = "0051_populate_documents"
down_revision = "0050_populate_maint_req"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

DOCS_TBL = "documents"
FOLDERS_TBL = "folders"
CSV_NAME = "documents.csv"

def _find_csv() -> Path | None:
    here = Path(__file__).resolve()
    candidates = [
        here.with_name(CSV_NAME),
        here.parent / "data" / CSV_NAME,
        here.parent.parent / "data" / CSV_NAME,
        Path(os.getenv("DOCUMENTS_CSV_PATH","")),
        Path.cwd() / CSV_NAME,
    ]
    for p in candidates:
        if p and str(p) != "" and p.exists():
            return p
    return None

def _parse_bool(s: str | None) -> bool | None:
    if s is None:
        return None
    v = s.strip().lower()
    if v in {"true","t","1","yes","y"}:
        return True
    if v in {"false","f","0","no","n"}:
        return False
    return None

def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    existing = set(insp.get_table_names(schema=None))
    missing = {DOCS_TBL, FOLDERS_TBL} - existing
    if missing:
        log.warning("[%s] missing tables: %s — aborting seed.", revision, sorted(missing))
        return

    csv_path = _find_csv()
    if not csv_path:
        log.warning("[%s] %s not found — aborting seed.", revision, CSV_NAME)
        return

    # lookups
    sel_folder = sa.text(f"SELECT id FROM {FOLDERS_TBL} WHERE lower(name)=lower(:name) LIMIT 1")

    # idempotence: treat (folder_id, title) as a natural key
    chk = sa.text(f"""
        SELECT 1 FROM {DOCS_TBL}
        WHERE COALESCE(folder_id,'00000000-0000-0000-0000-000000000000') = COALESCE(:folder_id,'00000000-0000-0000-0000-000000000000')
          AND lower(title) = lower(:title)
        LIMIT 1
    """)

    ins = sa.text(f"""
        INSERT INTO {DOCS_TBL}
        (id, folder_id, title, current_version_id, is_public, created_at, updated_at)
        VALUES (gen_random_uuid(), :folder_id, :title, :current_version_id, :is_public, now(), now())
    """).bindparams(
        sa.bindparam("folder_id"),
        sa.bindparam("title", type_=sa.String(255)),
        sa.bindparam("current_version_id"),
        sa.bindparam("is_public", type_=sa.Boolean),
    )

    inserted = skipped_missing_folder = skipped_dupes = 0
    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            folder_name = (row.get("folder_name") or "").strip()
            title = (row.get("title") or "").strip()
            if not title:
                continue

            folder_id = None
            if folder_name:
                folder_id = bind.execute(sel_folder, {"name": folder_name}).scalar()
            # It's valid for folder_id to be NULL; only log if a name was given but not found.
            if folder_name and not folder_id:
                skipped_missing_folder += 1
                continue

            current_version_id = (row.get("current_version_id") or "").strip() or None
            is_public = _parse_bool(row.get("is_public"))
            if is_public is None:
                is_public = False

            exists = bind.execute(chk, {"folder_id": folder_id, "title": title}).scalar()
            if exists:
                skipped_dupes += 1
                continue

            bind.execute(ins, {
                "folder_id": folder_id,
                "title": title,
                "current_version_id": current_version_id,
                "is_public": is_public,
            })
            inserted += 1

    log.info("[%s] inserted=%d, skipped_missing_folder=%d, skipped_dupes=%d",
             revision, inserted, skipped_missing_folder, skipped_dupes)

def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if DOCS_TBL not in insp.get_table_names(schema=None):
        return

    csv_path = _find_csv()
    if not csv_path:
        log.warning("[%s] downgrade skipped; %s not found.", revision, CSV_NAME)
        return

    titles = []
    with csv_path.open("r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            t = (row.get("title") or "").strip()
            if t:
                titles.append(t)

    if not titles:
        return

    del_stmt = sa.text(f"DELETE FROM {DOCS_TBL} WHERE title = ANY(:titles)")\
                 .bindparams(sa.bindparam("titles", value=titles, type_=pg.ARRAY(sa.String())))
    bind.execute(del_stmt)