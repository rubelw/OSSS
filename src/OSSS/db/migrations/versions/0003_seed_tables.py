# src/OSSS/db/migrations/versions/0003_seed_tables.py
from __future__ import annotations

import json
import os
import uuid
from typing import Any, Iterable
import logging
from datetime import datetime, date, timezone

from alembic import op, context
import sqlalchemy as sa
from sqlalchemy import Table, MetaData
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError, ProgrammingError, DataError
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.postgresql import UUID as PGUUID

# ---- Alembic identifiers ----
revision = "0003_seed_tables"
down_revision = "0002_add_tables"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

# --- Config -------------------------------------------------------------------
CANDIDATE_PATHS = [
    os.getenv("SEED_JSON_PATH"),
    os.path.join(os.path.dirname(__file__), "..", "data", "seed_full_school.json"),
    os.path.join(os.path.dirname(__file__), "..", "..", "seeds", "seed_full_school.json"),
    "/mnt/data/seed_full_school.json",
]


def _emit(msg: str) -> None:
    try:
        context.config.print_stdout(msg)
    except Exception:
        print(msg)


def _load_seed() -> tuple[list[str], dict[str, list[dict[str, Any]]]]:
    path = next((p for p in CANDIDATE_PATHS if p and os.path.exists(p)), None)
    if not path:
        raise RuntimeError(
            "Seed JSON not found. Set SEED_JSON_PATH or drop seed_full_school.json in one of:\n"
            + "\n".join(f"  - {p}" for p in CANDIDATE_PATHS if p)
        )

    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    if isinstance(payload, dict) and "data" in payload:
        insert_order = list(payload.get("insert_order") or payload["data"].keys())
        data = payload["data"]
    else:
        data = payload
        insert_order = list(data.keys())

    fixed: dict[str, list[dict[str, Any]]] = {}
    for table, rows in data.items():
        if rows is None:
            fixed[table] = []
        elif isinstance(rows, dict):
            fixed[table] = [rows]
        else:
            fixed[table] = list(rows)

    return insert_order, fixed


def _reflect_table(conn: Connection, name: str) -> Table | None:
    md = MetaData()
    try:
        return Table(name, md, autoload_with=conn)
    except Exception:
        return None


# ---- coercions ---------------------------------------------------------------

def _coerce_uuid(value: Any, *, table: str, column: str) -> uuid.UUID | None:
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return value
    s = str(value).strip()
    try:
        return uuid.UUID(s)
    except Exception:
        # Deterministic, so identical placeholders map consistently across rows
        return uuid.uuid5(uuid.NAMESPACE_URL, f"{table}.{column}:{s}")

def _coerce_datetime(value: Any) -> datetime | None:
    if value is None or isinstance(value, datetime):
        return value
    s = str(value).strip()
    # Accept ISO8601 with 'Z'
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(s)
    except Exception:
        try:
            # Fallback: seconds only
            return datetime.strptime(str(value), "%Y-%m-%d %H:%M:%S")
        except Exception:
            return None

def _coerce_date(value: Any) -> date | None:
    if value is None or isinstance(value, date) and not isinstance(value, datetime):
        return value
    s = str(value).split("T", 1)[0]
    try:
        return date.fromisoformat(s)
    except Exception:
        return None

def _coerce_bool(value: Any) -> bool | None:
    if value is None or isinstance(value, bool):
        return value
    s = str(value).strip().lower()
    if s in {"1", "true", "t", "yes", "y"}:
        return True
    if s in {"0", "false", "f", "no", "n"}:
        return False
    return None

def _coerce_int(value: Any) -> int | None:
    if value is None or isinstance(value, int) and not isinstance(value, bool):
        return value
    try:
        return int(str(value).strip())
    except Exception:
        return None


def _filter_and_coerce_row(table: Table, row: dict[str, Any]) -> dict[str, Any]:
    """
    Keep only known columns and coerce common types from JSON strings/placeholders
    (UUID, date, datetime, boolean, integer).
    """
    out: dict[str, Any] = {}
    for col in table.columns:
        name = col.name
        if name not in row:
            continue
        val = row[name]

        # UUID detection
        is_uuid_col = False
        try:
            is_uuid_col = isinstance(col.type, PGUUID) or (getattr(col.type, "python_type", None) is uuid.UUID)
        except Exception:
            pass

        if is_uuid_col:
            out[name] = _coerce_uuid(val, table=str(table.name), column=name)
            continue

        # Datetime / Date
        try:
            if isinstance(col.type, sa.DateTime):
                out[name] = _coerce_datetime(val)
                continue
            if isinstance(col.type, sa.Date):
                out[name] = _coerce_date(val)
                continue
        except Exception:
            pass

        # Boolean
        try:
            if isinstance(col.type, sa.Boolean):
                coerced = _coerce_bool(val)
                out[name] = bool(coerced) if coerced is not None else None
                continue
        except Exception:
            pass

        # Integer-ish
        try:
            if isinstance(col.type, (sa.Integer, sa.BigInteger, sa.SmallInteger)):
                coerced = _coerce_int(val)
                out[name] = coerced
                continue
        except Exception:
            pass

        # Default: pass through
        out[name] = val
    # Drop Nones for NOT NULL columns that also have server defaults (let DB fill)
    for col in table.columns:
        if out.get(col.name) is None and not col.nullable and col.server_default is not None:
            out.pop(col.name, None)
    return out


# ---- insert helpers ----------------------------------------------------------

def _insert_rows_batch(conn: Connection, table: Table, rows: list[dict[str, Any]]):
    """Single statement batch insert (with ON CONFLICT DO NOTHING on PG)."""
    if not rows:
        return
    is_pg = conn.dialect.name == "postgresql"
    pk_cols = [c for c in table.primary_key.columns]
    if is_pg and pk_cols:
        stmt = (
            pg_insert(table)
            .values(rows)
            .on_conflict_do_nothing(index_elements=[c.name for c in pk_cols])
        )
    else:
        stmt = sa.insert(table)
    if stmt is sa.insert(table):
        conn.execute(stmt, rows)
    else:
        conn.execute(stmt)


def _insert_row_single(conn: Connection, table: Table, row: dict[str, Any]):
    """Per-row insert with conflict-ignore semantics on PG."""
    is_pg = conn.dialect.name == "postgresql"
    pk_cols = [c for c in table.primary_key.columns]
    if is_pg and pk_cols:
        stmt = (
            pg_insert(table)
            .values(row)
            .on_conflict_do_nothing(index_elements=[c.name for c in pk_cols])
        )
    else:
        stmt = sa.insert(table).values(**row)
    conn.execute(stmt)


def upgrade() -> None:
    conn: Connection = op.get_bind()
    insert_order, data = _load_seed()

    for name in insert_order:
        tbl = _reflect_table(conn, name)
        if tbl is None:
            _emit(f"[seed] skip missing table: {name}")
            continue

        raw_rows = data.get(name, []) or []
        if not raw_rows:
            continue

        # Prepare & coerce
        prepared = []
        for r in raw_rows:
            coerced = _filter_and_coerce_row(tbl, r)
            if coerced:
                prepared.append(coerced)

        if not prepared:
            continue

        _emit(f"[seed] inserting into {name}: {len(prepared)} row(s)")

        # 1) Try batch inside its own savepoint
        try:
            with conn.begin_nested():  # create SAVEPOINT; auto rollback on error only to this point
                _insert_rows_batch(conn, tbl, prepared)
            continue  # success for this table
        except (IntegrityError, ProgrammingError, DataError) as e:
            _emit(
                f"[seed] batch insert failed for {name}: {e}; rolling back and retrying per-row"
            )

        # 2) Fall back to row-wise, each in its own savepoint; skip offenders
        for r in prepared:
            try:
                with conn.begin_nested():
                    _insert_row_single(conn, tbl, r)
            except (IntegrityError, ProgrammingError, DataError) as e:
                _emit(f"[seed] skipping row in {name}: {e}")

    # let Alembic commit the outer transaction


def downgrade() -> None:
    conn: Connection = op.get_bind()
    insert_order, data = _load_seed()

    for name in reversed(insert_order):
        tbl = _reflect_table(conn, name)
        if tbl is None:
            continue
        rows = data.get(name, []) or []
        if not rows:
            continue

        # Coerce so WHERE matches types
        prepared = [_filter_and_coerce_row(tbl, r) for r in rows]

        # Build PK-based delete in per-row savepoints to avoid aborting all on one FK
        for r in prepared:
            pk_cols = [c for c in tbl.primary_key.columns]
            if not pk_cols:
                continue
            if not all(col.name in r for col in pk_cols):
                continue
            cond = sa.and_(*[(col == r[col.name]) for col in pk_cols])
            try:
                with conn.begin_nested():
                    conn.execute(sa.delete(tbl).where(cond))
            except Exception as e:
                _emit(f"[seed] downgrade skip row in {name}: {e}")
