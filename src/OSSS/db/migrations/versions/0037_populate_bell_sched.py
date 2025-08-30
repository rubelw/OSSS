# versions/0036_populate_rooms.py
from __future__ import annotations

import csv
import logging
import os
from pathlib import Path
from datetime import datetime

from alembic import op
import sqlalchemy as sa

revision = "0037_populate_bell_sched"
down_revision = "0036_populate_rooms"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

STAGING_TABLE = "bell_schedules_import"


def _find_csv() -> Path:
    env = os.getenv("BELL_SCHEDULE_CSV")
    if env:
        p = Path(env).expanduser()
        if p.exists():
            return p
    here = Path(__file__).parent
    for cand in [here / "bell_schedule.csv", here.parent.parent.parent / "bell_schedule.csv"]:
        if cand.exists():
            return cand
    raise FileNotFoundError("bell_schedule.csv not found. Set BELL_SCHEDULE_CSV or place it near this migration.")


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

    # 1) staging table (has school_name from CSV)
    op.create_table(
        STAGING_TABLE,
        sa.Column("school_name", sa.Text, nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # reflect tables (no column specs; SQLA 2.x)
    bell_import = sa.Table(STAGING_TABLE, meta, autoload_with=bind)
    schools = sa.Table("schools", meta, autoload_with=bind)
    bell_schedules = sa.Table("bell_schedules", meta, autoload_with=bind)

    # 2) load CSV
    csv_path = _find_csv()
    rows = []
    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        # Expect: school_name, name, created_at, updated_at
        for r in reader:
            sname = (r.get("school_name") or "").strip()
            sched_name = (r.get("name") or "").strip()
            if not sname or not sched_name:
                continue
            rows.append(dict(
                school_name=sname,
                name=sched_name,
                created_at=_parse_dt(r.get("created_at")),
                updated_at=_parse_dt(r.get("updated_at")),
            ))

    if rows:
        bind.execute(sa.insert(bell_import), rows)

    # 3) insert into bell_schedules via JOIN on schools.name
    select_src = (
        sa.select(
            schools.c.id.label("school_id"),
            bell_import.c.name,
            bell_import.c.created_at,
            bell_import.c.updated_at,
        )
        .select_from(bell_import.join(schools, schools.c.name == bell_import.c.school_name))
    )
    insert_cols = ["school_id", "name", "created_at", "updated_at"]

    if bind.dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        stmt = pg_insert(bell_schedules).from_select(insert_cols, select_src).on_conflict_do_nothing()
        bind.execute(stmt)
    else:
        bind.execute(sa.insert(bell_schedules).from_select(insert_cols, select_src))

    # 4) drop staging
    op.drop_table(STAGING_TABLE)


def downgrade():
    # Data-only seed; not easily reversible
    pass