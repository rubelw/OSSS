"""Generic seed of sample data for ALL tables using reflection.

Revision ID: 0005_seed_all_sample_data
Revises: 0004_seed_sample_data
Create Date: 2025-08-24
"""
from __future__ import annotations

import logging
logger = logging.getLogger(__name__)

import random
import uuid
import datetime as dt
from collections import defaultdict, deque
from decimal import Decimal
from typing import Any, Dict, List, Mapping, Optional, Tuple

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection
from sqlalchemy.sql import sqltypes as sat


# ---- Alembic identifiers ----
revision = "0019_seed_remaining_tables"
down_revision = "0018_populate_positions"
branch_labels = None
depends_on = None

SEED_PREFIX = "__seed__"  # used to mark string values and allow safe downgrade filtering


# --- helper: never boolean-evaluate SQLAlchemy ClauseElements ---


def _get_table(metadata: sa.MetaData, name: str, schema: str | None, bind) -> sa.Table:
    """
    Return a reflected Table from this metadata. Try both schema-qualified and
    unqualified keys that SQLAlchemy stores in metadata.tables.
    """
    key = f"{schema}.{name}" if schema else name

    tbl = metadata.tables.get(key)
    if tbl is None and schema:
        # some dialects store unqualified key; try that too
        tbl = metadata.tables.get(name)

    if tbl is not None:
        return tbl

    # reflect into this metadata
    return sa.Table(name, metadata, schema=schema, autoload_with=bind)

def _enable_pgcrypto(conn) -> None:
    """Ensure pgcrypto extension exists on PostgreSQL; no-op on other DBs."""
    if conn.dialect.name == "postgresql":
        # use the same connection Alembic is running with
        conn.exec_driver_sql('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')


def _now_str() -> str:
    return dt.datetime.utcnow().isoformat(timespec="seconds")


def _rand_suffix(n: int = 6) -> str:
    return "".join(random.choice("abcdefghijklmnopqrstuvwxyz0123456789") for _ in range(n))


def _is_string_type(coltype) -> bool:
    return isinstance(coltype, (sat.String, sat.Text, sat.Unicode, sat.UnicodeText, sat.CHAR, sat.VARCHAR))


def _is_json_type(coltype) -> bool:
    return isinstance(coltype, (sat.JSON,))


def _is_numeric_type(coltype) -> bool:
    return isinstance(coltype, (sat.Integer, sat.BigInteger, sat.SmallInteger, sat.Numeric, sat.Float, sat.DECIMAL))


def _is_boolean_type(coltype) -> bool:
    return isinstance(coltype, (sat.Boolean,))


def _is_date_type(coltype) -> bool:
    return isinstance(coltype, (sat.Date,))


def _is_time_type(coltype) -> bool:
    return isinstance(coltype, (sat.Time,))


def _is_datetime_type(coltype) -> bool:
    return isinstance(coltype, (sat.DateTime, sat.TIMESTAMP))


def _is_uuidy_char36(col) -> bool:
    # Heuristic: common pattern in this DB is CHAR(36) for UUIDs
    return isinstance(col.type, sat.CHAR) and getattr(col.type, "length", None) == 36


def _server_default_exists(col) -> bool:
    # SQLAlchemy reflection often populates 'server_default' for explicit defaults
    return bool(getattr(col, "server_default", None))


def _gen_value_for_col(
    table: sa.Table,
    col: sa.Column,
    fk_map: Dict[str, Tuple[str, str]],
    seeded_rows: Dict[str, Mapping[str, Any]],
) -> Tuple[bool, Any]:
    """
    Returns (use_param, value_or_sql_fragment). If use_param is False, the returned value
    is an inline SQL fragment (e.g., 'now()'). Otherwise it's a Python value param.
    """
    name = col.name

    # Fill FK if possible
    if name in fk_map:
        parent_table, parent_col = fk_map[name]
        parent_row = seeded_rows.get(parent_table)
        if parent_row is not None and parent_col in parent_row:
            return True, parent_row[parent_col]
        # If we cannot satisfy FK yet and it's nullable, leave it out (caller may skip)
        if col.nullable:
            return True, None

    ctype = col.type

    # Prefer to omit columns that have a server default and are nullable (DB will fill)
    if _server_default_exists(col):
        return True, sa.sql.null()

    # Primary key handling
    if col.primary_key:
        # Composite PKs: we'll still make a value per column
        if _is_uuidy_char36(col) or (isinstance(ctype, sat.String) and getattr(ctype, "length", 0) >= 36):
            return True, str(uuid.uuid4())
        if _is_numeric_type(ctype):
            return True, 1
        if _is_string_type(ctype):
            # states.code or other short pks
            maxlen = getattr(ctype, "length", 64) or 64
            return True, (SEED_PREFIX + "_pk_" + _rand_suffix())[:maxlen]

    # Timestamps: inline now() for non-nullable, else None
    if _is_datetime_type(ctype):
        if col.nullable:
            return True, None
        return False, "now()"

    if _is_date_type(ctype):
        # Today +/- some days
        days = random.randint(-30, 30)
        d = (dt.date.today() + dt.timedelta(days=days)).isoformat()
        return True, d

    if _is_time_type(ctype):
        t = dt.time(hour=random.randint(7, 18), minute=random.choice([0, 15, 30, 45]), second=0).isoformat()
        return True, t

    if _is_boolean_type(ctype):
        return True, True

    if _is_numeric_type(ctype):
        if isinstance(ctype, sat.Numeric):
            return True, Decimal("1.00")
        return True, 1

    if _is_json_type(ctype):
        return True, {}

    if _is_string_type(ctype):
        maxlen = getattr(ctype, "length", None)
        base = f"{SEED_PREFIX}_{table.name}_{name}_{_rand_suffix()}"
        if maxlen:
            return True, base[:maxlen]
        return True, base

    # Fallbacks
    return True, None


def _get_fk_map(inspector, schema: Optional[str], table_name: str) -> Dict[str, Tuple[str, str]]:
    fk_map: Dict[str, Tuple[str, str]] = {}
    for fk in inspector.get_foreign_keys(table_name, schema=schema):
        cols = fk.get("constrained_columns", [])
        ref_table = fk.get("referred_table")
        ref_cols = fk.get("referred_columns", [])
        if ref_table and cols and ref_cols:
            for c, rc in zip(cols, ref_cols):
                fk_map[c] = (ref_table, rc)
    return fk_map


def _topo_sort_tables(inspector, schema: Optional[str], table_names: List[str]) -> List[str]:
    # Build dependency graph: child -> {parents}
    parents: Dict[str, set] = {t: set() for t in table_names}
    children: Dict[str, set] = {t: set() for t in table_names}

    for t in table_names:
        for fk in inspector.get_foreign_keys(t, schema=schema):
            rt = fk.get("referred_table")
            if rt and rt in parents:  # limit to our set
                parents[t].add(rt)
                children[rt].add(t)

    # Kahn's algorithm
    q = deque([t for t in table_names if not parents[t]])
    ordered: List[str] = []
    while q:
        n = q.popleft()
        ordered.append(n)
        for m in list(children[n]):
            parents[m].discard(n)
            children[n].discard(m)
            if not parents[m]:
                q.append(m)

    # If cycles remain, append the rest in any order (we'll try nullable FKs)
    remaining = [t for t in table_names if t not in ordered]
    return ordered + remaining


def _reflect_metadata(conn: Connection, schema: Optional[str]) -> sa.MetaData:
    md = sa.MetaData(schema=schema)
    md.reflect(bind=conn, schema=schema)
    return md


def _choose_str_col_for_marker(table: sa.Table) -> Optional[sa.Column]:
    # Prefer a common name-like column to tag with SEED_PREFIX for downgrade filtering
    pref = ["name", "title", "code", "label", "slug"]
    cols = {c.name: c for c in table.columns}
    for p in pref:
        c = cols.get(p)
        if c is not None and _is_string_type(c.type):
            return c
    # otherwise any string column
    for c in table.columns:
        if _is_string_type(c.type):
            return c
    return None


def _insert_one_row(
    conn: Connection,
    table: sa.Table,
    fk_map: Dict[str, Tuple[str, str]],
    seeded_rows: Dict[str, Mapping[str, Any]],
) -> Optional[Mapping[str, Any]]:
    cols: List[str] = []
    vals_sql: List[str] = []
    params: Dict[str, Any] = {}

    # We'll try to set a seed marker in one string column if possible
    marker_col = _choose_str_col_for_marker(table)

    for col in table.columns:
        # Skip auto-generated defaultable columns if nullable and has default
        # We'll still set for FKs and PKs explicitly
        use_param, value = _gen_value_for_col(table, col, fk_map, seeded_rows)

        # If the column is nullable and value is None and not PK, we can skip setting it
        if value is None and col.nullable and not col.primary_key and col.name not in fk_map:
            continue

        cols.append(sa.sql.column(col.name).name)

        if use_param:
            pname = f"p_{len(params)}"
            vals_sql.append(f":{pname}")
            params[pname] = value
        else:
            vals_sql.append(str(value))

    if not cols:
        return None  # nothing to insert?

    sql = f'insert into {table.name} ({", ".join(cols)}) values ({", ".join(vals_sql)}) returning *'
    res = conn.execute(text(sql), params)
    row = res.mappings().first()
    return dict(row) if row else None


def upgrade() -> None:
    conn = op.get_bind()
    metadata = sa.MetaData()

    _enable_pgcrypto(conn)
    inspector = inspect(conn)

    schema = None
    table_names = [t for t in inspector.get_table_names(schema=schema) if t != "alembic_version"]
    ordered = _topo_sort_tables(inspector, schema, table_names)

    seeded_rows: Dict[str, Mapping[str, Any]] = {}

    for tname in ordered:
        table = _get_table(metadata, tname, schema, conn)
        if table is None:
            continue

        fk_map = _get_fk_map(inspector, schema, tname)

        # IMPORTANT: let exceptions escape the nested transaction context,
        # so it can ROLLBACK the savepoint for us. Catch them outside.
        try:
            with conn.begin_nested():
                row = _insert_one_row(conn, table, fk_map, seeded_rows)
                if row:
                    seeded_rows[tname] = row
        except Exception as e:
            # Transaction for this table was rolled back cleanly by the ctx mgr.
            print(f"[seed] Skipped {tname}: {e}")

    # No explicit commit; Alembic manages the outer transaction

def _delete_seeded_rows(conn: Connection, table: sa.Table, marker_col: Optional[sa.Column]) -> int:
    if marker_col is None:
        # Try a generic heuristic: delete rows created very recently from 'created_at' if exists
        c_at = table.columns.get("created_at")
        if c_at is not None and _is_datetime_type(c_at.type):
            # 1 hour window (UTC)
            sql = text(f"delete from {table.name} where {c_at.name} >= (now() - interval '1 hour')")
            res = conn.execute(sql)
            return res.rowcount or 0
        return 0

    # Delete rows whose marker_col begins with our SEED_PREFIX
    sql = text(f"delete from {table.name} where {marker_col.name} like :pfx")
    res = conn.execute(sql, {"pfx": f"{SEED_PREFIX}%"})
    return res.rowcount or 0


def downgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    schema = None
    metadata = _reflect_metadata(conn, schema)

    # Reverse order to delete children first
    table_names = [t for t in inspector.get_table_names(schema=schema) if t != "alembic_version"]

    # A rough reverse topological order: compute topo and reverse it
    ordered = _topo_sort_tables(inspector, schema, table_names)[::-1]

    total_deleted = 0
    for tname in ordered:
        table = metadata.tables.get(f"{schema + '.' if schema else ''}{tname}") or metadata.tables.get(tname)
        if table is None:
            continue
        marker_col = _choose_str_col_for_marker(table)
        try:
            total_deleted += _delete_seeded_rows(conn, table, marker_col)
        except Exception as e:
            print(f"[seed-downgrade] Skipped {tname}: {e}")

    print(f"[seed-downgrade] deleted ~{total_deleted} rows across tables")
