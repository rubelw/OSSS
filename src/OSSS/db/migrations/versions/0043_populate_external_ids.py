"""Seed external_ids from external_ids.csv (schema-aware; idempotent; legacy table name tolerant)."""
from __future__ import annotations

import csv
import os
from pathlib import Path
from datetime import datetime

from alembic import op
import sqlalchemy as sa

# --- identifiers ---
revision = "0043_populate_external_ids"
down_revision = "0042_populate_gov_bodies"  # adjust if different
branch_labels = None
depends_on = None

STAGING_TABLE = "external_ids_import"


def _find_csv() -> Path:
    env = os.getenv("EXTERNAL_IDS_CSV")
    if env:
        p = Path(env).expanduser()
        if p.exists():
            return p
    here = Path(__file__).parent
    for cand in [here / "external_ids.csv", here.parent.parent.parent / "external_ids.csv"]:
        if cand.exists():
            return cand
    raise FileNotFoundError(
        "external_ids.csv not found. Set EXTERNAL_IDS_CSV or place it near this migration."
    )


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


def upgrade():
    bind = op.get_bind()
    meta = sa.MetaData()

    # 1) staging table
    op.create_table(
        STAGING_TABLE,
        sa.Column("entity_type", sa.Text, nullable=False),
        sa.Column("entity_id", sa.Text, nullable=False),  # import as text, cast later
        sa.Column("system", sa.Text, nullable=False),
        sa.Column("external_id", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    imp = sa.Table(STAGING_TABLE, meta, autoload_with=bind)
    target = sa.Table("external_ids", meta, autoload_with=bind)

    # 2) load CSV
    csv_path = _find_csv()
    rows = []
    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(
                dict(
                    entity_type=(r.get("entity_type") or "").strip(),
                    entity_id=(r.get("entity_id") or "").strip(),
                    system=(r.get("system") or "").strip(),
                    external_id=(r.get("external_id") or "").strip(),
                    created_at=_parse_dt(r.get("created_at")),
                    updated_at=_parse_dt(r.get("updated_at")),
                )
            )
    if rows:
        bind.execute(sa.insert(imp), rows)

    # 3) insert into target table (cast entity_id → target column type) using NOT EXISTS (no unique index required)
    colmap = {c.lower(): c for c in target.c.keys()}
    entity_id_col = target.c[colmap["entity_id"]]
    entity_type_col = target.c[colmap["entity_type"]] if "entity_type" in colmap else target.c.entity_type
    system_col = target.c[colmap["system"]] if "system" in colmap else target.c.system

    cast_entity_id = sa.cast(imp.c.entity_id, entity_id_col.type)

    not_exists = ~sa.exists().where(
        sa.and_(
            entity_type_col == imp.c.entity_type,
            system_col == imp.c.system,
            entity_id_col == cast_entity_id,
        )
    )

    insert_cols = ["entity_type", "entity_id", "system", "external_id", "created_at", "updated_at"]

    select_src = (
        sa.select(
            imp.c.entity_type,
            cast_entity_id.label("entity_id"),
            imp.c.system,
            imp.c.external_id,
            imp.c.created_at,
            imp.c.updated_at,
        )
        .where(not_exists)
    )

    bind.execute(sa.insert(target).from_select(insert_cols, select_src))

    # 4) drop staging
    op.drop_table(STAGING_TABLE)


def downgrade():
    # Data seed; not easily reversible
    pass
