"""Seed meetings from meetings.csv (schema-aware; idempotent; legacy name tolerant)."""
from __future__ import annotations

import csv
import os
from pathlib import Path
from datetime import datetime

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql.sqltypes import DateTime
try:
    from sqlalchemy.dialects.postgresql import TSVECTOR
except Exception:  # pragma: no cover
    TSVECTOR = type("_MissingTSVECTOR", (), {})  # harmless fallback

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
    if s in {"true", "t", "1", "yes", "y"}:
        return True
    if s in {"false", "f", "0", "no", "n"}:
        return False
    return None


def upgrade():
    bind = op.get_bind()
    meta = sa.MetaData()

    # Always start with a clean staging table (rerun-safe)
    try:
        op.execute(sa.text(f'DROP TABLE IF EXISTS "{STAGING_TABLE}"'))
    except Exception:
        pass

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

    try:
        imp = sa.Table(STAGING_TABLE, meta, autoload_with=bind)
        orgs = sa.Table("organizations", meta, autoload_with=bind)
        gb = sa.Table("governing_bodies", meta, autoload_with=bind)
        mtgs = sa.Table("meetings", meta, autoload_with=bind)

        # 2) Load CSV → staging
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
                rows.append(
                    dict(
                        org_code=org_code,
                        governing_body_name=(r.get("governing_body_name") or "").strip()
                        or None,
                        title=title,
                        starts_at=starts_at,
                        ends_at=_parse_dt(r.get("ends_at")),
                        location=(r.get("location") or "").strip() or None,
                        status=(r.get("status") or "").strip() or None,
                        is_public=_parse_bool(r.get("is_public")),
                        stream_url=(r.get("stream_url") or "").strip() or None,
                        created_at=_parse_dt(r.get("created_at")),
                        updated_at=_parse_dt(r.get("updated_at")),
                    )
                )

        if rows:
            bind.execute(sa.insert(imp), rows)

        # 3) Resolve org_code column on organizations (case-insensitive join)
        org_cols = {c.lower(): c for c in orgs.c.keys()}
        if "code" not in org_cols:
            raise RuntimeError(
                f"organizations table needs a 'code' column; found: {list(orgs.c.keys())}"
            )
        org_code_col = orgs.c[org_cols["code"]]

        j1 = sa.and_(sa.func.lower(org_code_col) == sa.func.lower(imp.c.org_code))
        j2 = sa.and_(
            gb.c.org_id == orgs.c.id,
            sa.func.lower(gb.c.name) == sa.func.lower(imp.c.governing_body_name),
        )

        # 4) Build schema-aware insert list with TYPE CHECKS
        present = {c.name: c for c in mtgs.c}

        def has_dt(colname: str) -> bool:
            col = present.get(colname)
            if col is None:
                return False
            return isinstance(col.type, DateTime)

        def is_textsearch(colname: str) -> bool:
            col = present.get(colname)
            return bool(col is not None and isinstance(col.type, TSVECTOR))

        expr_map = {
            "org_id": orgs.c.id.label("org_id"),
            "governing_body_id": sa.case(
                (imp.c.governing_body_name.is_(None), None), else_=gb.c.id
            ).label("governing_body_id"),
            "title": imp.c.title,
            # If target has 'scheduled_at', use starts_at for it.
            "scheduled_at": imp.c.starts_at.label("scheduled_at"),
            "starts_at": imp.c.starts_at,
            "ends_at": imp.c.ends_at,
            "location": imp.c.location,
            "status": imp.c.status,
            "is_public": sa.func.coalesce(imp.c.is_public, True).label("is_public"),
            "stream_url": imp.c.stream_url,
            # created_at / updated_at conditionally appended below
        }

        desired_order = [
            "org_id",
            "governing_body_id",
            "title",
            "scheduled_at",
            "starts_at",
            "ends_at",
            "location",
            "status",
            "is_public",
            "stream_url",
        ]

        insert_cols = [c for c in desired_order if c in present and c in expr_map]
        select_cols = [expr_map[c] for c in insert_cols]

        # Conditionally include created_at / updated_at if DateTime (not TSVECTOR, etc.)
        if "created_at" in present and has_dt("created_at") and not is_textsearch("created_at"):
            insert_cols.append("created_at")
            select_cols.append(imp.c.created_at)

        if "updated_at" in present and has_dt("updated_at") and not is_textsearch("updated_at"):
            insert_cols.append("updated_at")
            select_cols.append(imp.c.updated_at)

        if not insert_cols:
            raise RuntimeError(
                "[0044_populate_meetings] No matching insertable columns between CSV/staging and meetings table."
            )

        select_src = sa.select(*select_cols).select_from(
            imp.join(orgs, j1).outerjoin(gb, j2)
        )

        bind.execute(sa.insert(mtgs).from_select(insert_cols, select_src))

    finally:
        # Always drop staging (handles reruns cleanly)
        try:
            op.execute(sa.text(f'DROP TABLE IF EXISTS "{STAGING_TABLE}"'))
        except Exception:
            pass


def downgrade():
    # Not easily reversible (seed data)
    pass
