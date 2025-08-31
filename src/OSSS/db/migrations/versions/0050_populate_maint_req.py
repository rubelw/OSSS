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
revision = "0050_populate_maint_req"
down_revision = "0049_populate_waranties"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

CSV_NAME = "maintenance_requests.csv"

SCHOOLS_TBL   = "schools"
BUILDINGS_TBL = "buildings"
SPACES_TBL    = "spaces"
ASSETS_TBL    = "assets"
USERS_TBL     = "users"
WOS_TBL       = "work_orders"
MR_TBL        = "maintenance_requests"

def _find_csv(fname: str = CSV_NAME) -> Path | None:
    here = Path(__file__).resolve()
    candidates = [
        here.with_name(fname),
        here.parent / "data" / fname,
        here.parent.parent / "data" / fname,
        Path(os.getenv("MR_CSV_PATH","")),
        Path.cwd() / fname,
    ]
    for p in candidates:
        if p and str(p) != "" and p.exists():
            return p
    return None

def _parse_dt(s: str | None):
    if not s:
        return None
    s = s.strip()
    if not s:
        return None
    # Accept ISO-ish "YYYY-MM-DDTHH:MM:SSZ"
    try:
        if s.endswith("Z"):
            s = s[:-1]
        return datetime.fromisoformat(s)
    except Exception:
        return None

def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    needed = {SCHOOLS_TBL, BUILDINGS_TBL, SPACES_TBL, ASSETS_TBL, MR_TBL}
    missing = needed - set(insp.get_table_names(schema=None))
    if missing:
        log.warning("[%s] missing tables: %s — abort seeding.", revision, sorted(missing))
        return

    csv_path = _find_csv()
    if not csv_path:
        log.warning("[%s] %s not found — abort seeding.", revision, CSV_NAME)
        return

    # Lookups (case-insensitive). Tune if your schema differs.
    sel_school   = sa.text(f"SELECT id FROM {SCHOOLS_TBL}   WHERE lower(name)=lower(:name) LIMIT 1")
    sel_building = sa.text(f"SELECT id FROM {BUILDINGS_TBL} WHERE lower(name)=lower(:name) LIMIT 1")
    sel_space    = sa.text(f"SELECT id FROM {SPACES_TBL}    WHERE lower(name)=lower(:name) LIMIT 1")
    sel_asset    = sa.text(f"SELECT id FROM {ASSETS_TBL}    WHERE lower(tag)=lower(:tag)   LIMIT 1")
    sel_wo       = sa.text(f"SELECT id FROM {WOS_TBL}       WHERE id = :id LIMIT 1")

    # Idempotence: consider requests duplicates if same (summary, asset_id, created_at date)
    chk = sa.text(f"""
        SELECT 1 FROM {MR_TBL}
        WHERE summary=:summary
          AND COALESCE(asset_id,'00000000-0000-0000-0000-000000000000') = COALESCE(:asset_id,'00000000-0000-0000-0000-000000000000')
          AND DATE(created_at) = DATE(:created_at)
        LIMIT 1
    """)

    ins = sa.text(f"""
        INSERT INTO {MR_TBL}
        (id, school_id, building_id, space_id, asset_id, submitted_by_user_id,
         status, priority, summary, description, converted_work_order_id,
         attributes, created_at, updated_at)
        VALUES (gen_random_uuid(), :school_id, :building_id, :space_id, :asset_id, :submitted_by_user_id,
                :status, :priority, :summary, :description, :converted_work_order_id,
                :attributes, :created_at, :updated_at)
    """).bindparams(
        sa.bindparam("school_id"),
        sa.bindparam("building_id"),
        sa.bindparam("space_id"),
        sa.bindparam("asset_id"),
        sa.bindparam("submitted_by_user_id"),
        sa.bindparam("status", type_=sa.String(32)),
        sa.bindparam("priority", type_=sa.String(16)),
        sa.bindparam("summary", type_=sa.String(255)),
        sa.bindparam("description", type_=sa.Text),
        sa.bindparam("converted_work_order_id"),
        sa.bindparam("attributes", type_=pg.JSON()),
        sa.bindparam("created_at", type_=sa.DateTime(timezone=True)),
        sa.bindparam("updated_at", type_=sa.DateTime(timezone=True)),
    )

    inserted = skipped_no_refs = skipped_dupes = 0
    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            school_name   = (row.get("school_name") or "").strip()
            building_name = (row.get("building_name") or "").strip()
            space_name    = (row.get("space_name") or "").strip()
            asset_tag     = (row.get("asset_tag") or "").strip()

            school_id   = bind.execute(sel_school,   {"name": school_name}).scalar() if school_name else None
            building_id = bind.execute(sel_building, {"name": building_name}).scalar() if building_name else None
            space_id    = bind.execute(sel_space,    {"name": space_name}).scalar() if space_name else None
            asset_id    = bind.execute(sel_asset,    {"tag": asset_tag}).scalar()   if asset_tag else None

            status      = (row.get("status") or "new")[:32]
            priority    = (row.get("priority") or None)
            summary     = (row.get("summary") or "").strip()[:255]
            description = (row.get("description") or "").strip()
            cwo_raw     = (row.get("converted_work_order_id") or "").strip()
            converted_work_order_id = None
            if cwo_raw:
                # only accept if actually exists
                converted_work_order_id = bind.execute(sel_wo, {"id": cwo_raw}).scalar()

            attrs_raw = row.get("attributes") or ""
            try:
                attributes = json.loads(attrs_raw) if attrs_raw else None
            except json.JSONDecodeError:
                attributes = None

            created_at = _parse_dt(row.get("created_at")) or sa.text("now()")
            updated_at = _parse_dt(row.get("updated_at")) or sa.text("now()")

            # Optional: require at least one of (school_id, building_id, space_id, asset_id)
            if not any([school_id, building_id, space_id, asset_id]):
                skipped_no_refs += 1
                continue

            # Idempotence check
            ca_dt = created_at if isinstance(created_at, datetime) else datetime.utcnow()
            exists = bind.execute(chk, {"summary": summary, "asset_id": asset_id, "created_at": ca_dt}).scalar()
            if exists:
                skipped_dupes += 1
                continue

            bind.execute(ins, {
                "school_id": school_id,
                "building_id": building_id,
                "space_id": space_id,
                "asset_id": asset_id,
                "submitted_by_user_id": None,  # not provided in CSV; leave null
                "status": status,
                "priority": priority,
                "summary": summary,
                "description": description,
                "converted_work_order_id": converted_work_order_id,
                "attributes": attributes,
                "created_at": ca_dt,
                "updated_at": updated_at if isinstance(updated_at, datetime) else ca_dt,
            })
            inserted += 1

    log.info("[%s] inserted=%d, skipped_no_refs=%d, skipped_dupes=%d",
             revision, inserted, skipped_no_refs, skipped_dupes)

def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if MR_TBL not in insp.get_table_names(schema=None):
        return

    csv_path = _find_csv()
    if not csv_path:
        log.warning("[%s] downgrade skipped; %s not found.", revision, CSV_NAME)
        return

    # Best effort: delete rows matching the summaries in the CSV, from the time window
    summaries = []
    with csv_path.open("r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            s = (row.get("summary") or "").strip()
            if s:
                summaries.append(s)

    if not summaries:
        return

    del_stmt = sa.text(f"DELETE FROM {MR_TBL} WHERE summary = ANY(:summaries)")\
                 .bindparams(sa.bindparam("summaries", value=summaries, type_=pg.ARRAY(sa.String())))
    bind.execute(del_stmt)