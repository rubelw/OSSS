"""Seed governing_bodies from governing_bodies.csv (schema-aware; idempotent; legacy table name tolerant)."""
from __future__ import annotations

import csv
import os
from pathlib import Path
from datetime import datetime

from alembic import op
import sqlalchemy as sa

# --- identifiers ---
revision = "0045_populate_addresses"
down_revision = "0044_populate_meetings"  # adjust if different
branch_labels = None
depends_on = None

STAGING_TABLE = "addresses_import"


def _find_csv() -> Path:
    # Allow override via env var; otherwise look next to this migration or repo root
    env = os.getenv("ADDRESSES_CSV")
    if env:
        p = Path(env).expanduser()
        if p.exists():
            return p
    here = Path(__file__).parent
    for cand in [
        here / "addresses.csv",
        here.parent.parent.parent / "addresses.csv",  # ../../.. from versions/
    ]:
        if cand.exists():
            return cand
    raise FileNotFoundError(
        "addresses.csv not found. Set ADDRESSES_CSV or place it near this migration."
    )


def _parse_dt(x):
    if not x or str(x).strip().lower() == "null":
        return None
    s = str(x).strip().rstrip("Z")
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None


def upgrade():
    bind = op.get_bind()
    meta = sa.MetaData()

    # 1) Create staging table with all CSV columns as TEXT/DateTime
    op.create_table(
        STAGING_TABLE,
        sa.Column("line1", sa.Text, nullable=False),
        sa.Column("line2", sa.Text, nullable=True),
        sa.Column("city", sa.Text, nullable=False),
        sa.Column("state", sa.Text, nullable=True),
        sa.Column("postal_code", sa.Text, nullable=True),
        sa.Column("country", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    imp = sa.Table(STAGING_TABLE, meta, autoload_with=bind)
    addresses = sa.Table("addresses", meta, autoload_with=bind)

    # 2) Load CSV -> staging
    csv_path = _find_csv()
    rows = []
    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            line1 = (r.get("line1") or "").strip()
            city = (r.get("city") or "").strip()
            if not line1 or not city:
                continue
            rows.append(
                dict(
                    line1=line1,
                    line2=(r.get("line2") or "").strip() or None,
                    city=city,
                    state=(r.get("state") or "").strip() or None,
                    postal_code=(r.get("postal_code") or "").strip() or None,
                    country=(r.get("country") or "").strip() or None,
                    created_at=_parse_dt(r.get("created_at")),
                    updated_at=_parse_dt(r.get("updated_at")),
                )
            )
    if rows:
        bind.execute(sa.insert(imp), rows)

    # 3) Schema-aware insert (handles if some columns differ/missing)
    colmap = {c.lower(): c for c in addresses.c.keys()}
    def has(name: str) -> bool: return name.lower() in colmap
    def is_dt(name: str) -> bool:
        if not has(name): return False
        return isinstance(addresses.c[colmap[name.lower()]].type, sa.DateTime)

    insert_cols, select_exprs = [], []

    for name in ("line1", "line2", "city", "state", "postal_code", "country"):
        if has(name):
            insert_cols.append(colmap[name])
            select_exprs.append(getattr(imp.c, name))

    if has("created_at") and is_dt("created_at"):
        insert_cols.append(colmap["created_at"])
        select_exprs.append(imp.c.created_at)
    if has("updated_at") and is_dt("updated_at"):
        insert_cols.append(colmap["updated_at"])
        select_exprs.append(imp.c.updated_at)

    if not insert_cols:
        raise RuntimeError(f"addresses has no compatible columns. Found: {list(addresses.c.keys())}")

    select_src = sa.select(*select_exprs).select_from(imp)

    if bind.dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        stmt = pg_insert(addresses).from_select(insert_cols, select_src).on_conflict_do_nothing()
        bind.execute(stmt)
    else:
        bind.execute(sa.insert(addresses).from_select(insert_cols, select_src))

    # 4) Drop staging
    op.drop_table(STAGING_TABLE)


def downgrade():
    # Seed data migration; not easily reversible
    pass