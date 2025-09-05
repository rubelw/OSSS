# src/OSSS/db/migrations/versions/0003_seed_tables.py
from __future__ import annotations

import json
import os
import uuid
from typing import Any, Iterable
import logging

from alembic import op, context
import sqlalchemy as sa
from sqlalchemy import Table, MetaData
from sqlalchemy.engine import Connection
 # IntegrityError may be used but not fatal if linter complains
from sqlalchemy.exc import IntegrityError
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


def _coerce_uuid(value: Any, *, table: str, column: str) -> uuid.UUID | None:
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return value
    s = str(value).strip()
    try:
        return uuid.UUID(s)
    except Exception:
        # Deterministic UUID from table/column/value so refs match if placeholders are identical
        return uuid.uuid5(uuid.NAMESPACE_URL, f"{table}.{column}:{s}")


def _filter_and_coerce_row(table: Table, row: dict[str, Any]) -> dict[str, Any]:
    """
    Keep only known columns and coerce UUID-typed columns from strings/placeholders.
    (Add other coercions here as needed.)
    """
    out: dict[str, Any] = {}
    for col in table.columns:
        name = col.name
        if name not in row:
            continue
        val = row[name]

        # Try to detect UUID columns
        is_uuid_col = False
        try:
            is_uuid_col = isinstance(col.type, PGUUID) or (getattr(col.type, "python_type", None) is uuid.UUID)
        except Exception:
            # some SQLA types raise on python_type
            pass

        if is_uuid_col:
            out[name] = _coerce_uuid(val, table=str(table.name), column=name)
        else:
            out[name] = val
    return out


def _insert_rows(conn: Connection, table: Table, rows: Iterable[dict[str, Any]]):
    prepared_rows = []
    for r in rows:
        coerced = _filter_and_coerce_row(table, r)
        if coerced:
            prepared_rows.append(coerced)

    if not prepared_rows:
        return

    is_pg = conn.dialect.name == "postgresql"
    pk_cols = [c for c in table.primary_key.columns]

    try:
        if is_pg and pk_cols:
            stmt = (
                pg_insert(table)
                .values(prepared_rows)
                .on_conflict_do_nothing(index_elements=[c.name for c in pk_cols])
            )
            conn.execute(stmt)
        else:
            ins = sa.insert(table)
            try:
                conn.execute(ins, prepared_rows)
            except IntegrityError:
                for r in prepared_rows:
                    try:
                        conn.execute(ins.values(**r))
                    except IntegrityError:
                        pass
    except IntegrityError:
        # Ignore duplicate/idempotent errors so the migration can run multiple times
        pass


def _delete_rows(conn: Connection, table: Table, rows: Iterable[dict[str, Any]]):
    pk_cols = [c for c in table.primary_key.columns]
    if not pk_cols:
        return
    for r in rows:
        # Use raw row for delete matching; coerce UUIDs to match what we inserted
        r2 = _filter_and_coerce_row(table, r)
        if all(col.name in r2 for col in pk_cols):
            cond = sa.and_(*[(col == r2[col.name]) for col in pk_cols])
            conn.execute(sa.delete(table).where(cond))


def upgrade() -> None:
    conn: Connection = op.get_bind()
    insert_order, data = _load_seed()

    for name in insert_order:
        tbl = _reflect_table(conn, name)
        if tbl is None:
            _emit(f"[seed] skip missing table: {name}")
            continue
        rows = data.get(name, [])
        if not rows:
            continue
        _emit(f"[seed] inserting into {name}: {len(rows)} row(s)")
        _insert_rows(conn, tbl, rows)


def downgrade() -> None:
    conn: Connection = op.get_bind()
    insert_order, data = _load_seed()
    for name in reversed(insert_order):
        tbl = _reflect_table(conn, name)
        if tbl is None:
            continue
        rows = data.get(name, [])
        if not rows:
            continue
        _emit(f"[seed] deleting from {name}: {len(rows)} row(s)")
        _delete_rows(conn, tbl, rows)
