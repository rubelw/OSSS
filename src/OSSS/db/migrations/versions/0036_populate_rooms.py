# versions/0036_populate_rooms.py
from __future__ import annotations

import csv
import logging
import os
from pathlib import Path
from datetime import datetime

from alembic import op
import sqlalchemy as sa

revision = "0036_populate_rooms"
down_revision = "0035_populate_folders"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

STAGING_TABLE = "rooms_import"


def _parse_dt(x):
    """Return a timezone-naive datetime from ISO-like strings (tolerates trailing 'Z'), or None."""
    if not x or str(x).strip().lower() == "null":
        return None
    s = str(x).strip()
    if s.endswith("Z"):
        s = s[:-1]
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None


def _parse_int_like(x):
    """Return an int or None from messy CSV input ('72', '72.0', '', 'null')."""
    if x is None:
        return None
    s = str(x).strip()
    if not s or s.lower() == "null":
        return None
    try:
        return int(s)  # handles '72', '072', 72
    except ValueError:
        try:
            return int(float(s))  # handles '72.0', '72.5' -> 72 (truncate)
        except ValueError:
            return None


def _find_csv() -> Path:
    """
    Locate rooms.csv:
      1) $ROOMS_CSV (absolute or relative path)
      2) rooms.csv next to this migration file
      3) rooms.csv three levels up (repo root-ish)
    """
    env = os.getenv("ROOMS_CSV")
    if env:
        p = Path(env).expanduser()
        if p.exists():
            return p
    here = Path(__file__).parent
    for cand in [here / "rooms.csv", here.parent.parent.parent / "rooms.csv"]:
        if cand.exists():
            return cand
    raise FileNotFoundError("rooms.csv not found. Set ROOMS_CSV or place it next to this migration.")


def upgrade():
    bind = op.get_bind()
    meta = sa.MetaData()

    # 1) Create staging table (has school_name from CSV)
    op.create_table(
        STAGING_TABLE,
        sa.Column("school_name", sa.Text, nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("capacity", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Reflect staging + real tables (SQLAlchemy 2.x: reflect with autoload_with)
    rooms_import = sa.Table(STAGING_TABLE, meta, autoload_with=bind)
    schools = sa.Table("schools", meta, autoload_with=bind)  # reflect only, no column specs
    rooms = sa.Table("rooms", meta, autoload_with=bind)      # reflect only, no column specs

    # 2) Load CSV into staging
    csv_path = _find_csv()
    rows = []
    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        # Expect: school_name, name, capacity, created_at, updated_at
        for r in reader:
            sname = (r.get("school_name") or "").strip()
            room_name = (r.get("name") or "").strip()
            if not sname or not room_name:
                continue
            capacity = _parse_int_like(r.get("capacity"))
            rows.append(
                dict(
                    school_name=sname,
                    name=room_name,
                    capacity=capacity,
                    created_at=_parse_dt(r.get("created_at")),
                    updated_at=_parse_dt(r.get("updated_at")),
                )
            )

    if rows:
        bind.execute(sa.insert(rooms_import), rows)

    # 3) Insert into rooms by joining schools.name == rooms_import.school_name
    select_source = (
        sa.select(
            schools.c.id.label("school_id"),
            rooms_import.c.name,
            rooms_import.c.capacity,
            rooms_import.c.created_at,
            rooms_import.c.updated_at,
        )
        .select_from(rooms_import.join(schools, schools.c.name == rooms_import.c.school_name))
    )
    insert_cols = ["school_id", "name", "capacity", "created_at", "updated_at"]

    if bind.dialect.name == "postgresql":
        # Use ON CONFLICT DO NOTHING if a unique/PK would collide (adjust if you have a specific unique index)
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        stmt = pg_insert(rooms).from_select(insert_cols, select_source).on_conflict_do_nothing()
        bind.execute(stmt)
    else:
        bind.execute(sa.insert(rooms).from_select(insert_cols, select_source))

    # 4) Drop staging table
    op.drop_table(STAGING_TABLE)


def downgrade():
    # Data seed; not easily reversible
    pass
