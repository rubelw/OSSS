# versions/0038_populate_spec_ed_cases.py
from __future__ import annotations

import csv
import logging
import os
from pathlib import Path
from datetime import datetime, date

from alembic import op
import sqlalchemy as sa

revision = "0038_populate_spec_ed_cases"
down_revision = "0037_populate_bell_sched"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

STAGING_TABLE = "special_education_cases_import"


def _find_csv() -> Path:
    env = os.getenv("SPECIAL_ED_CASES_CSV")
    if env:
        p = Path(env).expanduser()
        if p.exists():
            return p
    here = Path(__file__).parent
    for cand in [here / "special_education_cases.csv", here.parent.parent.parent / "special_education_cases.csv"]:
        if cand.exists():
            return cand
    raise FileNotFoundError(
        "special_education_cases.csv not found. Set SPECIAL_ED_CASES_CSV or place it near this migration."
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


def _parse_date(x):
    if not x:
        return None
    s = str(x).strip()
    if not s or s.lower() == "null":
        return None
    try:
        return date.fromisoformat(s)  # YYYY-MM-DD
    except Exception:
        return None


def upgrade():
    bind = op.get_bind()
    meta = sa.MetaData()

    # 1) Staging table with name parts
    op.create_table(
        STAGING_TABLE,
        sa.Column("first_name", sa.Text, nullable=False),
        sa.Column("middle_name", sa.Text, nullable=True),
        sa.Column("last_name", sa.Text, nullable=False),
        sa.Column("eligibility", sa.Text, nullable=True),
        sa.Column("case_opened", sa.Date, nullable=True),
        sa.Column("case_closed", sa.Date, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Reflect real tables (no column specs)
    imp = sa.Table(STAGING_TABLE, meta, autoload_with=bind)
    persons = sa.Table("persons", meta, autoload_with=bind)
    students = sa.Table("students", meta, autoload_with=bind)
    cases = sa.Table("special_education_cases", meta, autoload_with=bind)

    log.info("persons columns: %s", list(persons.c.keys()))
    log.info("students columns: %s", list(students.c.keys()))
    log.info("cases columns: %s", list(cases.c.keys()))

    # 2) Load CSV → staging
    csv_path = _find_csv()
    rows = []
    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        # Expect: first_name, middle_name, last_name, eligibility, case_opened, case_closed, created_at, updated_at
        for r in reader:
            fn = (r.get("first_name") or "").strip()
            ln = (r.get("last_name") or "").strip()
            if not fn or not ln:
                continue
            rows.append(
                dict(
                    first_name=fn,
                    middle_name=(r.get("middle_name") or "").strip() or None,
                    last_name=ln,
                    eligibility=(r.get("eligibility") or "").strip() or None,
                    case_opened=_parse_date(r.get("case_opened")),
                    case_closed=_parse_date(r.get("case_closed")),
                    created_at=_parse_dt(r.get("created_at")),
                    updated_at=_parse_dt(r.get("updated_at")),
                )
            )
    if rows:
        bind.execute(sa.insert(imp), rows)

    # 3) Join: staging → persons (names), then persons → students (person_id)
    lower = sa.func.lower
    coalesce = sa.func.coalesce

    # persons has first_name, middle_name (nullable), last_name per your model
    join_imp_person = sa.and_(
        lower(persons.c.first_name) == lower(imp.c.first_name),
        lower(persons.c.last_name) == lower(imp.c.last_name),
        coalesce(lower(persons.c.middle_name), "") == coalesce(lower(imp.c.middle_name), ""),
    )

    # students.person_id -> persons.id
    join_person_student = students.c.person_id == persons.c.id

    select_src = (
        sa.select(
            students.c.id.label("student_id"),
            imp.c.eligibility,
            imp.c.case_opened,
            imp.c.case_closed,
            imp.c.created_at,
            imp.c.updated_at,
        )
        .select_from(
            imp.join(persons, join_imp_person).join(students, join_person_student)
        )
    )

    insert_cols = ["student_id", "eligibility", "case_opened", "case_closed", "created_at", "updated_at"]

    if bind.dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        stmt = pg_insert(cases).from_select(insert_cols, select_src).on_conflict_do_nothing()
        bind.execute(stmt)
    else:
        bind.execute(sa.insert(cases).from_select(insert_cols, select_src))

    # 4) Drop staging
    op.drop_table(STAGING_TABLE)


def downgrade():
    # Data seed; not easily reversible
    pass
