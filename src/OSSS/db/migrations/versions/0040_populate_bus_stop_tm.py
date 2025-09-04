"""Seed bus_stops from bus_stops.csv using route name lookup (schema-aware insert)."""
from __future__ import annotations

import csv
import os
from pathlib import Path
from datetime import datetime

from alembic import op
import sqlalchemy as sa

# --- identifiers ---
revision = "0040_populate_bus_stop_tm"
down_revision = "0039_populate_bus_stops"  # adjust if different
branch_labels = None
depends_on = None

STAGING_TABLE = "bus_stop_times_import"


def _find_csv() -> Path:
    env = os.getenv("BUS_STOP_TIMES_CSV")
    if env:
        p = Path(env).expanduser()
        if p.exists():
            return p
    here = Path(__file__).parent
    for cand in [here / "bus_stop_times.csv", here.parent.parent.parent / "bus_stop_times.csv"]:
        if cand.exists():
            return cand
    raise FileNotFoundError("bus_stop_times.csv not found. Set BUS_STOP_TIMES_CSV or place it near this migration.")


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
        sa.Column("stop_name", sa.Text, nullable=False),
        sa.Column("arrival_time", sa.Text, nullable=False),      # store as text in staging; convert on insert
        sa.Column("departure_time", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    imp = sa.Table(STAGING_TABLE, meta, autoload_with=bind)
    routes = sa.Table("bus_routes", meta, autoload_with=bind)
    stops = sa.Table("bus_stops", meta, autoload_with=bind)
    times = sa.Table("bus_stop_times", meta, autoload_with=bind)

    # 2) Load CSV rows
    csv_path = _find_csv()
    rows = []
    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rname = (r.get("route_name") or "").strip()
            sname = (r.get("stop_name") or "").strip()
            at = _parse_time(r.get("arrival_time"))
            if not rname or not sname or not at:
                continue
            rows.append(dict(
                route_name=rname,
                stop_name=sname,
                arrival_time=at,
                departure_time=_parse_time(r.get("departure_time")),
                created_at=_parse_dt(r.get("created_at")),
                updated_at=_parse_dt(r.get("updated_at")),
            ))
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

    # 4) Join staging -> routes (route_name) -> stops (route_id + stop name)
    lower = sa.func.lower

    join_imp_routes = lower(r_name) == lower(imp.c.route_name)
    join_routes_stops = sa.and_(
        stops.c.route_id == routes.c.id,
        lower(stops.c.name) == lower(imp.c.stop_name),
    )

    # --- CAST text -> TIME for arrival/departure to satisfy DB column types ---
    arr_expr = sa.cast(imp.c.arrival_time, sa.Time())
    dep_expr = sa.cast(imp.c.departure_time, sa.Time())

    # Base SELECT of rows we *want* to insert
    select_src = (
        sa.select(
            routes.c.id.label("route_id"),
            stops.c.id.label("stop_id"),
            arr_expr.label("arrival_time"),
            dep_expr.label("departure_time"),
            imp.c.created_at,
            imp.c.updated_at,
        )
        .select_from(imp.join(routes, join_imp_routes).join(stops, join_routes_stops))
    )

    # ---- FIX: avoid ON CONFLICT; use NOT EXISTS so we don't need a unique index ----
    not_exists = ~sa.exists(
        sa.select(sa.literal(1))
        .select_from(times)
        .where(
            sa.and_(
                times.c.route_id == routes.c.id,
                times.c.stop_id == stops.c.id,
                times.c.arrival_time == arr_expr,
            )
        )
    )
    select_src = select_src.where(not_exists)

    # Perform INSERT FROM SELECT (works on PG & SQLite)
    insert_cols = ["route_id", "stop_id", "arrival_time", "departure_time", "created_at", "updated_at"]
    bind.execute(sa.insert(times).from_select(insert_cols, select_src))

    # 5) Drop staging
    op.drop_table(STAGING_TABLE)


def downgrade():
    # Data seed; not easily reversible
    pass
