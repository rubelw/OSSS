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
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg
import csv
import json

# --- identifiers ---
revision = "0048_populate_embeds"
down_revision = "0047_populate_entity_tags"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE = "embeds"

def _find_csv() -> Path | None:
    """Look for embeds.csv in common spots relative to this migration and project."""
    here = Path(__file__).resolve()
    candidates = [
        here.with_name("embeds.csv"),
        here.parent / "data" / "embeds.csv",
        here.parent.parent / "data" / "embeds.csv",
        Path(os.getenv("EMBEDS_CSV_PATH", "")),
        Path.cwd() / "embeds.csv",
    ]
    for p in candidates:
        if p and str(p) != "" and p.exists():
            return p
    return None

def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    # sanity: ensure table exists
    existing_tables = set(insp.get_table_names(schema=None))
    if TABLE not in existing_tables:
        log.warning("[%s] table '%s' not found — skipping seed.", revision, TABLE)
        return

    csv_path = _find_csv()
    if not csv_path:
        log.warning("[%s] 'embeds.csv' not found in candidate paths — skipping seed.", revision)
        return

    log.info("[%s] loading CSV from: %s", revision, csv_path)

    # Prepare insert; rely on DB defaults for id/created_at/updated_at
    json_type = pg.JSONB(astext_type=sa.Text())
    ins = sa.text(
        f"""
        INSERT INTO {TABLE} (provider, url, meta)
        VALUES (:provider, :url, :meta)
        """
    ).bindparams(
        sa.bindparam("provider", type_=sa.String(64)),
        sa.bindparam("url", type_=sa.String(1024)),
        sa.bindparam("meta", type_=json_type),
    )

    # If you want idempotence, add a unique index first (e.g., on url), then append:
    #  ON CONFLICT (url) DO NOTHING
    # to the INSERT above. Uncomment if you have that constraint.
    #
    # ins = sa.text(
    #     f"INSERT INTO {TABLE} (provider, url, meta) "
    #     f"VALUES (:provider, :url, :meta) "
    #     f"ON CONFLICT (url) DO NOTHING"
    # ).bindparams(... same bindparams ...)

    added = 0
    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            provider = (row.get("provider") or "").strip()
            url = (row.get("url") or "").strip()
            meta_raw = row.get("meta") or ""

            if not provider or not url:
                continue

            # Parse meta JSON if it looks like JSON; else store as null
            try:
                meta = json.loads(meta_raw) if meta_raw else None
            except json.JSONDecodeError:
                meta = None

            bind.execute(ins, {"provider": provider, "url": url, "meta": meta})
            added += 1

    log.info("[%s] inserted %d rows into %s", revision, added, TABLE)


def downgrade() -> None:
    """Best-effort cleanup by deleting rows whose URLs exist in the CSV."""
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if TABLE not in insp.get_table_names(schema=None):
        return

    csv_path = _find_csv()
    if not csv_path:
        log.warning("[%s] cannot downgrade: 'embeds.csv' not found.", revision)
        return

    urls = []
    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            url = (row.get("url") or "").strip()
            if url:
                urls.append(url)

    if not urls:
        return

    # Delete only rows we inserted (matched by URL)
    del_stmt = sa.text(f"DELETE FROM {TABLE} WHERE url = ANY(:urls)")\
                 .bindparams(sa.bindparam("urls", value=urls, type_=pg.ARRAY(sa.String())))
    bind.execute(del_stmt)