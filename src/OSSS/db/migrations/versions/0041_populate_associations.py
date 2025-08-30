"""Seed bus_stops from bus_stops.csv using route name lookup (schema-aware insert)."""
from __future__ import annotations

import csv
import os
from pathlib import Path
from datetime import datetime

from alembic import op
import sqlalchemy as sa

# --- identifiers ---
revision = "0041_populate_associations"
down_revision = "0040_populate_bus_stop_tm"  # adjust if different
branch_labels = None
depends_on = None

STAGING_TABLE = "education_associations_import"


def _find_csv() -> Path:
    env = os.getenv("ASSOCIATIONS_CSV")
    if env:
        p = Path(env).expanduser()
        if p.exists():
            return p
    here = Path(__file__).parent
    for cand in [here / "associations.csv", here.parent.parent.parent / "associations.csv"]:
        if cand.exists():
            return cand
    raise FileNotFoundError("associations.csv not found. Set ASSOCIATIONS_CSV or place it near this migration.")


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
    if not x:
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

    # 1) Staging table
    op.create_table(
        STAGING_TABLE,
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("contact", sa.JSON, nullable=True),
        sa.Column("attributes", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    imp = sa.Table(STAGING_TABLE, meta, autoload_with=bind)
    associations = sa.Table("education_associations", meta, autoload_with=bind)

    # 2) Load CSV -> staging
    csv_path = _find_csv()
    rows = []
    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            name = (r.get("name") or "").strip()
            if not name:
                continue
            rows.append(
                dict(
                    name=name,
                    contact=_parse_json(r.get("contact")),
                    attributes=_parse_json(r.get("attributes")),
                    created_at=_parse_dt(r.get("created_at")),
                    updated_at=_parse_dt(r.get("updated_at")),
                )
            )
    if rows:
        bind.execute(sa.insert(imp), rows)

    # 3) Schema/type-aware insert columns
    assoc_colmap = {cname.lower(): cname for cname in associations.c.keys()}

    def col_exists(name: str) -> bool:
        return name.lower() in assoc_colmap

    def is_datetime_col(name: str) -> bool:
        """Only treat as datetime if SQLA sees a DateTime-ish type."""
        if not col_exists(name):
            return False
        col = associations.c[assoc_colmap[name.lower()]]
        # SQLAlchemy uses DateTime; dialects subclass it. Be permissive:
        return isinstance(col.type, sa.DateTime)

    # Always try these first
    insert_cols = []
    select_exprs = []

    if col_exists("name"):
        insert_cols.append(assoc_colmap["name"])
        select_exprs.append(imp.c.name)

    if col_exists("contact"):
        insert_cols.append(assoc_colmap["contact"])
        select_exprs.append(imp.c.contact)

    if col_exists("attributes"):
        insert_cols.append(assoc_colmap["attributes"])
        select_exprs.append(imp.c.attributes)

    # Only include timestamps if the target column is actually datetime
    if col_exists("created_at") and is_datetime_col("created_at"):
        insert_cols.append(assoc_colmap["created_at"])
        select_exprs.append(imp.c.created_at)

    if col_exists("updated_at") and is_datetime_col("updated_at"):
        insert_cols.append(assoc_colmap["updated_at"])
        select_exprs.append(imp.c.updated_at)

    if not insert_cols:
        raise RuntimeError(
            "education_associations has no compatible columns to insert into. "
            f"Found: {list(associations.c.keys())}"
        )

    select_src = sa.select(*select_exprs).select_from(imp)

    # 4) Insert; de-dupe by unique name if present
    if bind.dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        if col_exists("name"):
            stmt = (
                pg_insert(associations)
                .from_select(insert_cols, select_src)
                .on_conflict_do_nothing(index_elements=[assoc_colmap["name"]])
            )
        else:
            stmt = pg_insert(associations).from_select(insert_cols, select_src)
        bind.execute(stmt)
    else:
        bind.execute(sa.insert(associations).from_select(insert_cols, select_src))

    # 5) Drop staging
    op.drop_table(STAGING_TABLE)


def downgrade():
    # Data seed; not easily reversible
    pass