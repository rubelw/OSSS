"""Seed bus_stops from bus_stops.csv using route name lookup (schema-aware insert)."""
from __future__ import annotations

import csv
import os
from pathlib import Path
from datetime import datetime

from alembic import op
import sqlalchemy as sa

# --- identifiers ---
revision = "0039_populate_bus_stops"
down_revision = "0038_populate_spec_ed_cases"  # adjust if different
branch_labels = None
depends_on = None

STAGING_TABLE = "bus_stops_import"


def _find_csv() -> Path:
    env = os.getenv("BUS_STOPS_CSV")
    if env:
        p = Path(env).expanduser()
        if p.exists():
            return p
    here = Path(__file__).parent
    for cand in [here / "bus_stops.csv", here.parent.parent.parent / "bus_stops.csv"]:
        if cand.exists():
            return cand
    raise FileNotFoundError("bus_stops.csv not found. Set BUS_STOPS_CSV or place it near this migration.")


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


def _parse_time(x):
    if not x:
        return None
    s = str(x).strip()
    if not s or s.lower() == "null":
        return None
    try:
        hh, mm = s.split(":")[0:2]
        return f"{int(hh):02d}:{int(mm):02d}"
    except Exception:
        return None


def upgrade():
    bind = op.get_bind()
    meta = sa.MetaData()

    # 1) staging table
    op.create_table(
        STAGING_TABLE,
        sa.Column("route_name", sa.Text, nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("sequence", sa.Integer, nullable=True),
        sa.Column("latitude", sa.Float, nullable=True),
        sa.Column("longitude", sa.Float, nullable=True),
        sa.Column("pickup_time", sa.Text, nullable=True),
        sa.Column("dropoff_time", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    imp = sa.Table(STAGING_TABLE, meta, autoload_with=bind)
    routes = sa.Table("bus_routes", meta, autoload_with=bind)
    stops = sa.Table("bus_stops", meta, autoload_with=bind)

    # 2) load CSV
    csv_path = _find_csv()
    rows = []
    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rname = (r.get("route_name") or "").strip()
            name = (r.get("name") or "").strip()
            if not rname or not name:
                continue

            def _float(v):
                try:
                    return float(v) if v not in (None, "", "null") else None
                except Exception:
                    return None

            def _int(v):
                try:
                    return int(float(v)) if v not in (None, "", "null") else None
                except Exception:
                    return None

            rows.append(
                dict(
                    route_name=rname,
                    name=name,
                    sequence=_int(r.get("sequence")),
                    latitude=_float(r.get("latitude")),
                    longitude=_float(r.get("longitude")),
                    pickup_time=_parse_time(r.get("pickup_time")),
                    dropoff_time=_parse_time(r.get("dropoff_time")),
                    created_at=_parse_dt(r.get("created_at")),
                    updated_at=_parse_dt(r.get("updated_at")),
                )
            )

    if rows:
        bind.execute(sa.insert(imp), rows)

    # 3) resolve route name column on routes
    route_cols = {c.lower(): c for c in routes.c.keys()}

    def any_col(*cands: str):
        for c in cands:
            real = route_cols.get(c.lower())
            if real:
                return routes.c[real]
        return None

    r_name = any_col("name", "route_name", "route", "title")
    if r_name is None:
        raise RuntimeError(f"Could not find a route name column on bus_routes. Present: {list(routes.c.keys())}")

    # 4) build dynamic insert column list based on actual bus_stops schema
    stops_cols = {c.lower(): c for c in stops.c.keys()}

    # Required columns we will always insert
    insert_cols = ["route_id", "name"]
    select_exprs = [
        routes.c.id.label("route_id"),
        imp.c.name,
    ]

    # Optional: sequence → support common alternates
    if "sequence" in stops_cols:
        insert_cols.append("sequence")
        select_exprs.append(imp.c.sequence)
    elif "stop_order" in stops_cols:
        insert_cols.append("stop_order")
        select_exprs.append(imp.c.sequence.label("stop_order"))
    elif "position" in stops_cols:
        insert_cols.append("position")
        select_exprs.append(imp.c.sequence.label("position"))
    # else: table has no ordering column; skip

    # Optional passthroughs, only if present on bus_stops
    for opt in ["latitude", "longitude", "pickup_time", "dropoff_time", "created_at", "updated_at"]:
        if opt in stops_cols:
            insert_cols.append(opt)
            select_exprs.append(getattr(imp.c, opt))

    select_src = (
        sa.select(*select_exprs)
        .select_from(imp.join(routes, sa.func.lower(r_name) == sa.func.lower(imp.c.route_name)))
    )

    if bind.dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        stmt = pg_insert(stops).from_select(insert_cols, select_src).on_conflict_do_nothing()
        bind.execute(stmt)
    else:
        bind.execute(sa.insert(stops).from_select(insert_cols, select_src))

    # 5) drop staging
    op.drop_table(STAGING_TABLE)


def downgrade():
    # Data seed; not easily reversible
    pass
