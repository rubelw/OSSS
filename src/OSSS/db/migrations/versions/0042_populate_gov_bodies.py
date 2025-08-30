"""Seed governing_bodies from governing_bodies.csv (schema-aware; idempotent; legacy table name tolerant)."""
from __future__ import annotations

import csv
import os
from pathlib import Path
from datetime import datetime

from alembic import op
import sqlalchemy as sa

# --- identifiers ---
revision = "0042_populate_gov_bodies"
down_revision = "0041_populate_associations"  # adjust if different
branch_labels = None
depends_on = None

STAGING_TABLE = "governing_bodies_import"


def _find_csv() -> Path:
    env = os.getenv("GOVERNING_BODIES_CSV")
    if env:
        p = Path(env).expanduser()
        if p.exists():
            return p
    here = Path(__file__).parent
    for cand in [here / "governing_bodies.csv", here.parent.parent.parent / "governing_bodies.csv"]:
        if cand.exists():
            return cand
    raise FileNotFoundError("governing_bodies.csv not found. Set GOVERNING_BODIES_CSV or place it near this migration.")


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
    insp = sa.inspect(bind)

    # 0) Clean up any previous failed run
    try:
        op.execute(sa.text(f'DROP TABLE IF EXISTS "{STAGING_TABLE}"'))
    except Exception:
        pass

    try:
        # 1) staging table (org_id kept as TEXT; it's an org *code* in your CSV)
        op.create_table(
            STAGING_TABLE,
            sa.Column("org_id", sa.Text, nullable=False),   # org *code* from CSV
            sa.Column("name", sa.Text, nullable=False),
            sa.Column("type", sa.Text, nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        )

        imp = sa.Table(STAGING_TABLE, meta, autoload_with=bind)

        # 2) Resolve target table (support legacy name 'bodies')
        target_table_name = "governing_bodies" if insp.has_table("governing_bodies") else "bodies"
        bodies = sa.Table(target_table_name, meta, autoload_with=bind)

        # also reflect organizations so we can look up the UUID by code/name/id text
        orgs = sa.Table("organizations", meta, autoload_with=bind)

        # 3) Load CSV into staging
        csv_path = _find_csv()
        rows = []
        with csv_path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                org_code = (r.get("org_id") or "").strip()  # this is actually org code
                name = (r.get("name") or "").strip()
                if not org_code or not name:
                    continue
                rows.append(
                    dict(
                        org_id=org_code,
                        name=name,
                        type=(r.get("type") or "").strip() or None,
                        created_at=_parse_dt(r.get("created_at")),
                        updated_at=_parse_dt(r.get("updated_at")),
                    )
                )
        if rows:
            bind.execute(sa.insert(imp), rows)

        # 4) schema-aware column mapping (in case names/types differ)
        colmap = {c.lower(): c for c in bodies.c.keys()}

        def has(name: str) -> bool:
            return name.lower() in colmap

        def is_dt(name: str) -> bool:
            if not has(name):
                return False
            return isinstance(bodies.c[colmap[name.lower()]].type, sa.DateTime)

        insert_cols = []
        select_exprs = []

        # Build a JOIN to resolve the org UUID by CSV 'org_id' (which is org code).
        # Match precedence: organizations.code (primary), then name, then id::text
        lower = sa.func.lower
        join_cond = sa.or_(
            lower(orgs.c.code) == lower(imp.c.org_id),
            lower(orgs.c.name) == lower(imp.c.org_id),
            sa.cast(orgs.c.id, sa.Text) == imp.c.org_id,
        )
        sel_from = imp.join(orgs, join_cond)

        # org_id → use organizations.id (UUID), do NOT cast CSV text
        if has("org_id"):
            insert_cols.append(colmap["org_id"])
            select_exprs.append(orgs.c.id.label(colmap["org_id"]))

        # name
        if has("name"):
            insert_cols.append(colmap["name"])
            select_exprs.append(imp.c.name)

        # type
        if has("type"):
            insert_cols.append(colmap["type"])
            select_exprs.append(imp.c.type)

        # timestamps only if target columns are DateTime
        if has("created_at") and is_dt("created_at"):
            insert_cols.append(colmap["created_at"])
            select_exprs.append(imp.c.created_at)
        if has("updated_at") and is_dt("updated_at"):
            insert_cols.append(colmap["updated_at"])
            select_exprs.append(imp.c.updated_at)

        if not insert_cols:
            raise RuntimeError(f"{target_table_name} has no compatible columns. Found: {list(bodies.c.keys())}")

        select_src = sa.select(*select_exprs).select_from(sel_from)

        # 5) Insert (best-effort dedupe on PG)
        if bind.dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import insert as pg_insert
            stmt = pg_insert(bodies).from_select(insert_cols, select_src).on_conflict_do_nothing()
            bind.execute(stmt)
        else:
            bind.execute(sa.insert(bodies).from_select(insert_cols, select_src))

    finally:
        # 6) Always drop staging; swallow errors if transaction already aborted
        try:
            op.execute(sa.text(f'DROP TABLE IF EXISTS "{STAGING_TABLE}"'))
        except Exception:
            pass


def downgrade():
    # Data seed; not easily reversible
    pass
