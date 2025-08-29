"""add states table and seed from CSV

Revision ID: 0003_populate_states_table
Revises: 0002_add_tables
Create Date: 2025-08-15 00:00:00
"""
from __future__ import annotations

import os
import csv
from typing import List, Dict

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as psql
from sqlalchemy import text

# revision identifiers
revision = "0003_populate_states_table"
down_revision = "0002_add_tables"
branch_labels = None
depends_on = None


# -------- helpers ------------------------------------------------------------

def _has_table(bind, name: str) -> bool:
    insp = sa.inspect(bind)
    return insp.has_table(name)

def _table_states(metadata: sa.MetaData) -> sa.Table:
    # local table metadata (no need to import app models)
    return sa.Table(
        "states",
        metadata,
        sa.Column("code", sa.String(2), primary_key=True),
        sa.Column("name", sa.String(64), nullable=False, unique=True),
    )

def _choose_csv_path() -> str:
    """Prefer -x states_csv=..., else states.csv in this migration dir."""
    xargs = op.get_context().get_x_argument(as_dictionary=True)
    if "states_csv" in xargs and xargs["states_csv"]:
        return xargs["states_csv"]
    # default: file alongside this migration script
    here = os.path.dirname(__file__)
    return os.path.join(here, "states.csv")

def _load_states_from_csv(path: str) -> List[Dict[str, str]]:
    if not os.path.exists(path):
        raise RuntimeError(
            f"states.csv not found at '{path}'. "
            "Place a CSV with headers (code,name) next to this migration "
            "or pass -x states_csv=/absolute/path.csv"
        )

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        # normalize header keys once
        field_map = {k.lower().strip(): k for k in reader.fieldnames or []}

        # acceptable header aliases
        code_key = next(
            (field_map[k] for k in ("code", "abbr", "state_code") if k in field_map),
            None,
        )
        name_key = next(
            (field_map[k] for k in ("name", "state") if k in field_map),
            None,
        )
        if not code_key or not name_key:
            raise RuntimeError(
                f"states.csv must include 'code' (or abbr/state_code) and 'name' (or state) headers. "
                f"Found headers: {reader.fieldnames}"
            )

        rows: List[Dict[str, str]] = []
        for row in reader:
            code = (row.get(code_key) or "").strip()
            name = (row.get(name_key) or "").strip()
            if not code or not name:
                continue
            if len(code) != 2:
                # allow CSVs that have lowercase; store uppercase
                code = code[:2].upper()
            rows.append({"code": code.upper(), "name": name})
        if not rows:
            raise RuntimeError("states.csv contained no usable rows.")
        return rows


# -------- upgrade / downgrade ------------------------------------------------

def upgrade():
    bind = op.get_bind()
    md = sa.MetaData()
    states = _table_states(md)

    # Create the table if missing
    if not _has_table(bind, "states"):
        op.create_table(*states.columns)

    # Load CSV rows
    csv_path = _choose_csv_path()
    rows = _load_states_from_csv(csv_path)

    # Upsert rows
    if bind.dialect.name == "postgresql":
        ins = psql.insert(states).values(rows)
        upsert = ins.on_conflict_do_update(
            index_elements=[states.c.code],
            set_={"name": ins.excluded.name},
        )
        bind.execute(upsert)
    else:
        # generic fallback: delete then bulk insert
        for r in rows:
            bind.execute(text("DELETE FROM states WHERE code = :c"), {"c": r["code"]})
        op.bulk_insert(states, rows)


def downgrade():
    """Conservative rollback: remove the seeded rows but keep the table."""
    bind = op.get_bind()
    if not _has_table(bind, "states"):
        return

    try:
        rows = _load_states_from_csv(_choose_csv_path())
        codes = [r["code"] for r in rows]
    except Exception:
        # If CSV isn't available during downgrade, just do nothing.
        return

    # Delete only the seeded codes
    for c in codes:
        bind.execute(text("DELETE FROM states WHERE code = :c"), {"c": c})

    # If you want to drop the table entirely (only if this migration created it),
    # uncomment the next line:
    # op.drop_table("states")

def _has_column(bind, table: str, column: str) -> bool:
    insp = sa.inspect(bind)
    if not insp.has_table(table):
        return False
    return any(col["name"] == column for col in insp.get_columns(table))

def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)

    # Create the table if truly missing (choose one design: code as PK is simplest)
    if not insp.has_table("states"):
        op.create_table(
            "states",
            sa.Column("code", sa.String(2), primary_key=True),
            sa.Column("name", sa.String(64), nullable=False, unique=True),
        )

    # Ensure a unique constraint on code if it's not the PK (safe if PK)
    if bind.dialect.name == "postgresql":
        op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'uq_states_code'
            ) THEN
                BEGIN
                    ALTER TABLE states ADD CONSTRAINT uq_states_code UNIQUE (code);
                EXCEPTION WHEN duplicate_object THEN
                    -- already unique/primary key; ignore
                END;
            END IF;
        END$$;
        """)

    # Always upsert the rows
    op.execute("""
    INSERT INTO states (code, name) VALUES
    ('AL','Alabama'),('AK','Alaska'),('AZ','Arizona'),('AR','Arkansas'),
    ('CA','California'),('CO','Colorado'),('CT','Connecticut'),('DE','Delaware'),
    ('FL','Florida'),('GA','Georgia'),('HI','Hawaii'),('ID','Idaho'),
    ('IL','Illinois'),('IN','Indiana'),('IA','Iowa'),('KS','Kansas'),
    ('KY','Kentucky'),('LA','Louisiana'),('ME','Maine'),('MD','Maryland'),
    ('MA','Massachusetts'),('MI','Michigan'),('MN','Minnesota'),('MS','Mississippi'),
    ('MO','Missouri'),('MT','Montana'),('NE','Nebraska'),('NV','Nevada'),
    ('NH','New Hampshire'),('NJ','New Jersey'),('NM','New Mexico'),('NY','New York'),
    ('NC','North Carolina'),('ND','North Dakota'),('OH','Ohio'),('OK','Oklahoma'),
    ('OR','Oregon'),('PA','Pennsylvania'),('RI','Rhode Island'),('SC','South Carolina'),
    ('SD','South Dakota'),('TN','Tennessee'),('TX','Texas'),('UT','Utah'),
    ('VT','Vermont'),('VA','Virginia'),('WA','Washington'),('WV','West Virginia'),
    ('WI','Wisconsin'),('WY','Wyoming'),('DC','District of Columbia')
    ON CONFLICT (code) DO UPDATE SET name = EXCLUDED.name;
    """)

def downgrade():
    # conservative rollback: drop uniques and 'code' column if we added it
    bind = op.get_bind()
    if _has_table(bind, "states"):
        op.execute("ALTER TABLE states DROP CONSTRAINT IF EXISTS uq_states_code;")
        op.execute("ALTER TABLE states DROP CONSTRAINT IF EXISTS uq_states_name;")
        if _has_column(bind, "states", "code"):
            op.drop_column("states", "code")
        # If this migration originally created the table in your env, you can drop it:
        # op.drop_table("states")