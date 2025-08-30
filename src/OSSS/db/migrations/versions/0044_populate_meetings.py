"""Seed governing_bodies from governing_bodies.csv (schema-aware; idempotent; legacy table name tolerant)."""
from __future__ import annotations

import csv
import os
from pathlib import Path
from datetime import datetime

from alembic import op
import sqlalchemy as sa

# --- identifiers ---
revision = "0044_populate_meetings"
down_revision = "0043_populate_external_ids"  # adjust if different
branch_labels = None
depends_on = None

STAGING_TABLE = "meetings_import"

def _find_csv() -> Path:
    env = os.getenv("MEETINGS_CSV")
    if env:
        p = Path(env).expanduser()
        if p.exists():
            return p
    here = Path(__file__).parent
    for cand in [here / "meetings.csv", here.parent.parent.parent / "meetings.csv"]:
        if cand.exists():
            return cand
    raise FileNotFoundError(
        "meetings.csv not found. Set MEETINGS_CSV or place it near this migration."
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

def _parse_bool(x):
    if x is None:
        return None
    s = str(x).strip().lower()
    if s in {"true", "t", "1", "yes", "y"}: return True
    if s in {"false", "f", "0", "no", "n"}: return False
    return None

def upgrade():
    bind = op.get_bind()
    meta = sa.MetaData()

    # 1) Staging table
    op.create_table(
        STAGING_TABLE,
        sa.Column("org_code", sa.Text, nullable=False),
        sa.Column("governing_body_name", sa.Text, nullable=True),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("location", sa.Text, nullable=True),
        sa.Column("status", sa.Text, nullable=True),
        sa.Column("is_public", sa.Boolean, nullable=True),
        sa.Column("stream_url", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    imp  = sa.Table(STAGING_TABLE, meta, autoload_with=bind)
    orgs = sa.Table("organizations",     meta, autoload_with=bind)
    gb   = sa.Table("governing_bodies",  meta, autoload_with=bind)
    mtgs = sa.Table("meetings",          meta, autoload_with=bind)

    # 2) Load CSV
    csv_path = _find_csv()
    rows = []
    with csv_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            org_code = (r.get("org_code") or "").strip()
            title = (r.get("title") or "").strip()
            starts_at = _parse_dt(r.get("starts_at"))
            if not org_code or not title or not starts_at:
                continue
            rows.append(dict(
                org_code=org_code,
                governing_body_name=(r.get("governing_body_name") or "").strip() or None,
                title=title,
                starts_at=starts_at,
                ends_at=_parse_dt(r.get("ends_at")),
                location=(r.get("location") or "").strip() or None,
                status=(r.get("status") or "").strip() or None,
                is_public=_parse_bool(r.get("is_public")),
                stream_url=(r.get("stream_url") or "").strip() or None,
                created_at=_parse_dt(r.get("created_at")),
                updated_at=_parse_dt(r.get("updated_at")),
            ))

    if rows:
        bind.execute(sa.insert(imp), rows)

    # 3) Resolve columns likely present
    org_cols = {c.lower(): c for c in orgs.c.keys()}
    if "code" not in org_cols:
        raise RuntimeError(f"organizations table needs a 'code' column; found: {list(orgs.c.keys())}")
    org_code_col = orgs.c[org_cols["code"]]

    # Join staging -> organizations (by code)
    j1 = sa.and_(sa.func.lower(org_code_col) == sa.func.lower(imp.c.org_code))

    # Optional join to governing_bodies by (org_id, name) if governing_body_name present
    j2 = sa.and_(
        gb.c.org_id == orgs.c.id,
        sa.func.lower(gb.c.name) == sa.func.lower(imp.c.governing_body_name)
    )

    # Build select of resolved FKs, keeping null for governing_body_id if no name provided
    select_src = (
        sa.select(
            orgs.c.id.label("org_id"),
            sa.case(
                (imp.c.governing_body_name.is_(None), None),
                else_=gb.c.id
            ).label("governing_body_id"),
            imp.c.title,
            imp.c.starts_at,
            imp.c.ends_at,
            imp.c.location,
            imp.c.status,
            sa.func.coalesce(imp.c.is_public, True).label("is_public"),
            imp.c.stream_url,
            imp.c.created_at,
            imp.c.updated_at,
        )
        .select_from(
            imp.join(orgs, j1).outerjoin(gb, j2)
        )
    )

    insert_cols = [
        "org_id", "governing_body_id", "title", "starts_at", "ends_at",
        "location", "status", "is_public", "stream_url", "created_at", "updated_at"
    ]

    # 4) Insert (no ON CONFLICT because meetings likely have no unique natural key)
    bind.execute(sa.insert(mtgs).from_select(insert_cols, select_src))

    # 5) Drop staging
    op.drop_table(STAGING_TABLE)

def downgrade():
    # Not easily reversible (seed data)
    pass