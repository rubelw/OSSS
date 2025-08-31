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
revision = "0049_populate_waranties"
down_revision = "0048_populate_embeds"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")


ASSETS_TBL = "assets"
VENDORS_TBL = "vendors"
WARRANTIES_TBL = "warranties"

def _find_csv() -> Path | None:
    here = Path(__file__).resolve()
    candidates = [
        here.with_name("warranties.csv"),
        here.parent / "data" / "warranties.csv",
        here.parent.parent / "data" / "warranties.csv",
        Path(os.getenv("WARRANTIES_CSV_PATH","")),
        Path.cwd() / "warranties.csv",
    ]
    for p in candidates:
        if p and str(p) != "" and p.exists():
            return p
    return None

def _parse_date(s: str | None):
    if not s:
        return None
    s = s.strip()
    if not s:
        return None
    # Accept YYYY-MM-DD
    return datetime.strptime(s, "%Y-%m-%d").date()

def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)

    required = {ASSETS_TBL, VENDORS_TBL, WARRANTIES_TBL}
    existing = set(insp.get_table_names(schema=None))
    missing = required - existing
    if missing:
        log.warning("[%s] missing tables: %s — aborting seed.", revision, sorted(missing))
        return

    csv_path = _find_csv()
    if not csv_path:
        log.warning("[%s] warranties.csv not found — aborting seed.", revision)
        return

    log.info("[%s] loading warranties from %s", revision, csv_path)

    # Pre-compile statements
    sel_asset = sa.text(f"SELECT id FROM {ASSETS_TBL} WHERE lower(tag)=lower(:tag) LIMIT 1")
    sel_vendor = sa.text(f"SELECT id FROM {VENDORS_TBL} WHERE lower(name)=lower(:name) LIMIT 1")
    # Idempotence check: (asset_id, policy_no) as a natural-ish key
    chk_warranty = sa.text(
        f"SELECT 1 FROM {WARRANTIES_TBL} WHERE asset_id=:asset_id AND policy_no=:policy_no LIMIT 1"
    )
    ins_warranty = sa.text(
        f"""
        INSERT INTO {WARRANTIES_TBL}
        (id, asset_id, vendor_id, policy_no, start_date, end_date, terms, attributes, created_at, updated_at)
        VALUES (gen_random_uuid(), :asset_id, :vendor_id, :policy_no, :start_date, :end_date,
                :terms, :attributes, now(), now())
        """
    )

    json_type = pg.JSON(astext_type=sa.Text())  # or JSONB if your column is JSONB

    added, skipped_no_asset, skipped_dup = 0, 0, 0

    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            asset_tag = (row.get("asset_tag") or "").strip()
            vendor_name = (row.get("vendor_name") or "").strip()
            policy_no = (row.get("policy_no") or "").strip()
            start_date = _parse_date(row.get("start_date"))
            end_date = _parse_date(row.get("end_date"))
            terms = (row.get("terms") or "").strip()
            attrs_raw = row.get("attributes") or ""

            if not asset_tag or not policy_no:
                continue

            # lookups
            asset_id = bind.execute(sel_asset, {"tag": asset_tag}).scalar()
            if not asset_id:
                skipped_no_asset += 1
                continue
            vendor_id = None
            if vendor_name:
                vendor_id = bind.execute(sel_vendor, {"name": vendor_name}).scalar()

            # idempotence check
            exists = bind.execute(chk_warranty, {"asset_id": asset_id, "policy_no": policy_no}).scalar()
            if exists:
                skipped_dup += 1
                continue

            try:
                attributes = json.loads(attrs_raw) if attrs_raw else None
            except json.JSONDecodeError:
                attributes = None

            bind.execute(
                ins_warranty.bindparams(
                    sa.bindparam("asset_id"),
                    sa.bindparam("vendor_id"),
                    sa.bindparam("policy_no", type_=sa.String(128)),
                    sa.bindparam("start_date", type_=sa.Date),
                    sa.bindparam("end_date", type_=sa.Date),
                    sa.bindparam("terms", type_=sa.Text),
                    sa.bindparam("attributes", type_=json_type),
                ),
                {
                    "asset_id": asset_id,
                    "vendor_id": vendor_id,
                    "policy_no": policy_no,
                    "start_date": start_date,
                    "end_date": end_date,
                    "terms": terms,
                    "attributes": attributes,
                },
            )
            added += 1

    log.info("[%s] inserted=%d, skipped_no_asset=%d, skipped_dupes=%d",
             revision, added, skipped_no_asset, skipped_dup)

def downgrade():
    # Best effort: delete rows for policy_nos present in the CSV
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if WARRANTIES_TBL not in insp.get_table_names(schema=None):
        return

    csv_path = _find_csv()
    if not csv_path:
        log.warning("[%s] downgrade skipped; warranties.csv not found.", revision)
        return

    policy_nos = []
    with csv_path.open("r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            p = (row.get("policy_no") or "").strip()
            if p:
                policy_nos.append(p)

    if not policy_nos:
        return

    del_stmt = sa.text(f"DELETE FROM {WARRANTIES_TBL} WHERE policy_no = ANY(:pols)")\
                 .bindparams(sa.bindparam("pols", value=policy_nos, type_=pg.ARRAY(sa.String())))
    bind.execute(del_stmt)