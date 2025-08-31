"""Seed governing_bodies from governing_bodies.csv (schema-aware; idempotent; legacy table name tolerant)."""
from __future__ import annotations

import csv
import os
from pathlib import Path
from datetime import datetime

from alembic import op
import sqlalchemy as sa

# --- identifiers ---
revision = "0046_pm_plans"
down_revision = "0045_populate_addresses"  # adjust if different
branch_labels = None
depends_on = None

STAGING_TABLE = "pm_plans_import"


def _find_csv() -> Path:
    env = os.getenv("PM_PLANS_CSV")
    if env:
        p = Path(env).expanduser()
        if p.exists():
            return p
    here = Path(__file__).parent
    for cand in [
        here / "pm_plans.csv",
        here.parent.parent.parent / "pm_plans.csv",
    ]:
        if cand.exists():
            return cand
    raise FileNotFoundError("pm_plans.csv not found. Set PM_PLANS_CSV or place it near this migration.")


def _parse_dt(x):
    if not x or str(x).strip().lower() == "null":
        return None
    s = str(x).strip()
    if s.endswith("Z"):
        s = s[:-1]
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None


def _parse_json(x):
    if x is None:
        return None
    s = str(x).strip()
    if not s or s.lower() == "null":
        return None
    try:
        return json.loads(s)
    except Exception:
        return None


def upgrade():
    bind = op.get_bind()
    meta = sa.MetaData()

    # 1) Create staging table (store identifiers as text; JSON as text → cast later)
    op.create_table(
        STAGING_TABLE,
        sa.Column("asset_tag", sa.Text, nullable=False),
        sa.Column("facility_name", sa.Text, nullable=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("frequency", sa.Text, nullable=True),
        sa.Column("next_due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("active", sa.Boolean, nullable=True),
        sa.Column("procedure", sa.Text, nullable=True),
        sa.Column("attributes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    imp = sa.Table(STAGING_TABLE, meta, autoload_with=bind)
    assets = sa.Table("assets", meta, autoload_with=bind)
    buildings = sa.Table("buildings", meta, autoload_with=bind)
    pm_plans = sa.Table("pm_plans", meta, autoload_with=bind)

    # 2) Load CSV
    csv_path = _find_csv()
    rows = []
    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        # Columns expected from generated csv:
        # asset_tag, facility_name, name, frequency, next_due_at, last_completed_at,
        # active, procedure (json), attributes (json), created_at, updated_at
        for r in reader:
            tag = (r.get("asset_tag") or "").strip()
            nm = (r.get("name") or "").strip()
            if not tag or not nm:
                continue
            rows.append(
                dict(
                    asset_tag=tag,
                    facility_name=(r.get("facility_name") or "").strip() or None,
                    name=nm,
                    frequency=(r.get("frequency") or "").strip() or None,
                    next_due_at=_parse_dt(r.get("next_due_at")),
                    last_completed_at=_parse_dt(r.get("last_completed_at")),
                    active=(str(r.get("active")).strip().lower() in {"1", "true", "t", "yes", "y"}),
                    procedure=(r.get("procedure") or "").strip() or None,
                    attributes=(r.get("attributes") or "").strip() or None,
                    created_at=_parse_dt(r.get("created_at")),
                    updated_at=_parse_dt(r.get("updated_at")),
                )
            )
    if rows:
        bind.execute(sa.insert(imp), rows)

    # 3) Column discovery for assets and buildings
    # assets: need a tag-like column to match against
    asset_cols = {c.lower(): c for c in assets.c.keys()}
    tag_col = None
    for cand in ("tag", "asset_tag", "barcode", "code", "name"):
        if cand.lower() in asset_cols:
            tag_col = assets.c[asset_cols[cand.lower()]]
            break
    if tag_col is None:
        raise RuntimeError(f"Could not find a tag-like column on assets. Columns: {list(assets.c.keys())}")

    # buildings: prefer "facility_name" then "name"
    bld_cols = {c.lower(): c for c in buildings.c.keys()}
    bld_name_col = None
    for cand in ("facility_name", "name", "building_name", "title"):
        if cand.lower() in bld_cols:
            bld_name_col = buildings.c[bld_cols[cand.lower()]]
            break
    # bld_name_col may be None (if no building provided in CSV rows); we handle via LEFT JOIN

    lower = sa.func.lower

    # 4) Build SELECT with lookups
    select_list = [
        assets.c.id.label("asset_id"),
        imp.c.name,
        imp.c.frequency,
        imp.c.next_due_at,
        imp.c.last_completed_at,
        imp.c.active,
        # Cast JSON text into proper JSON type on PG; on others we can leave as text
    ]

    # Handle JSON casting
    if bind.dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import JSONB
        select_list += [
            sa.cast(imp.c.procedure, JSONB).label("procedure"),
            sa.cast(imp.c.attributes, JSONB).label("attributes"),
        ]
    else:
        select_list += [imp.c.procedure, imp.c.attributes]

    select_list += [imp.c.created_at, imp.c.updated_at]

    # Join assets by tag
    join_assets = lower(tag_col) == lower(imp.c.asset_tag)

    # Optional join to buildings by name
    if bld_name_col is not None:
        join_buildings = lower(bld_name_col) == lower(imp.c.facility_name)
        select_list.insert(1, buildings.c.id.label("building_id"))  # after asset_id
        from_clause = (
            imp.join(assets, join_assets).outerjoin(buildings, join_buildings)
        )
    else:
        # No building name column found → insert NULL for building_id
        select_list.insert(1, sa.literal(None).label("building_id"))
        from_clause = imp.join(assets, join_assets)

    select_src = sa.select(*select_list).select_from(from_clause)

    insert_cols = [
        "asset_id",
        "building_id",
        "name",
        "frequency",
        "next_due_at",
        "last_completed_at",
        "active",
        "procedure",
        "attributes",
        "created_at",
        "updated_at",
    ]

    # 5) Insert, ignore duplicates if unique constraints exist
    if bind.dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        stmt = pg_insert(pm_plans).from_select(insert_cols, select_src).on_conflict_do_nothing()
        bind.execute(stmt)
    else:
        bind.execute(sa.insert(pm_plans).from_select(insert_cols, select_src))

    # 6) Drop staging
    op.drop_table(STAGING_TABLE)


def downgrade():
    # Seed data; not easily reversible
    pass