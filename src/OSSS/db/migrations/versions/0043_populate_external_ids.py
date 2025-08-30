"""Seed governing_bodies from governing_bodies.csv (schema-aware; idempotent; legacy table name tolerant)."""
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
    raise FileNotFoundError("external_ids.csv not found. Set EXTERNAL_IDS_CSV or place it near this migration.")


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

    # 3) insert into target table (cast entity_id → UUID)
    colmap = {c.lower(): c for c in target.c.keys()}

    insert_cols = ["entity_type", "entity_id", "system", "external_id", "created_at", "updated_at"]

    select_src = sa.select(
        imp.c.entity_type,
        sa.cast(imp.c.entity_id, target.c[colmap["entity_id"]].type),
        imp.c.system,
        imp.c.external_id,
        imp.c.created_at,
        imp.c.updated_at,
    ).select_from(imp)

    if bind.dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        stmt = pg_insert(target).from_select(insert_cols, select_src).on_conflict_do_nothing(
            index_elements=["entity_type", "entity_id", "system"]
        )
        bind.execute(stmt)
    else:
        bind.execute(sa.insert(target).from_select(insert_cols, select_src))

    # 4) drop staging
    op.drop_table(STAGING_TABLE)


def downgrade():
    # Data seed; not easily reversible
    pass