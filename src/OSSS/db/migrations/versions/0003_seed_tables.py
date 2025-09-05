from __future__ import annotations

from __future__ import annotations
import json
import os
from typing import Any, Iterable
import logging
from alembic import op
import sqlalchemy as sa
from sqlalchemy import Table, MetaData
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError
from sqlalchemy.inspection import inspect as sa_inspect
from sqlalchemy.dialects.postgresql import insert as pg_insert  # safe to import; only used on PG

# ---- Alembic identifiers ----
revision = "0003_seed_tables"
down_revision = "0002_add_tables"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")


SEED_JSON_PATH = "./seed_full_school.json"

# --- Config -------------------------------------------------------------------
# You can override with env var: SEED_JSON_PATH=/path/to/seed_full_school.json
CANDIDATE_PATHS = [
    os.getenv("SEED_JSON_PATH"),
    os.path.join(os.path.dirname(__file__), "..", "data", "seed_full_school.json"),
    os.path.join(os.path.dirname(__file__), "..", "..", "seeds", "seed_full_school.json"),
    "/mnt/data/seed_full_school.json",  # handy for local runs with your earlier export
]


def _load_seed() -> tuple[list[str], dict[str, list[dict[str, Any]]]]:
    path = next((p for p in CANDIDATE_PATHS if p and os.path.exists(p)), None)
    if not path:
        raise RuntimeError(
            "Seed JSON not found. Set SEED_JSON_PATH or drop seed_full_school.json in one of:\n"
            + "\n".join(f"  - {p}" for p in CANDIDATE_PATHS if p)
        )

    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    # Support the format produced earlier:
    # { "insert_order": [...], "data": { "<table>": [ {row}, ... ], ... } }
    if isinstance(payload, dict) and "data" in payload:
        insert_order = list(payload.get("insert_order") or payload["data"].keys())
        data = payload["data"]
    else:
        # Fallback: assume top-level is { "<table>": [rows] }
        data = payload
        insert_order = list(data.keys())

    # Normalize rows to lists
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


def _filter_row_for_table(tbl: Table, row: dict[str, Any]) -> dict[str, Any]:
    cols = set(c.name for c in tbl.columns)
    # keep only columns that actually exist on the table
    return {k: v for k, v in row.items() if k in cols}


def _insert_rows(conn: Connection, table: Table, rows: Iterable[dict[str, Any]]):
    rows = [r for r in ( _filter_row_for_table(table, r) for r in rows ) if r]
    if not rows:
        return

    is_pg = conn.dialect.name == "postgresql"
    pk_cols = [c for c in table.primary_key.columns]  # list[Column]
    try:
        if is_pg and pk_cols:
            stmt = (
                pg_insert(table)
                .values(rows)
                .on_conflict_do_nothing(index_elements=pk_cols)
            )
            conn.execute(stmt)
        else:
            # generic path; tolerate duplicates by row
            ins = sa.insert(table)
            try:
                conn.execute(ins, rows)  # executemany
            except IntegrityError:
                # fall back to per-row best-effort
                for r in rows:
                    try:
                        conn.execute(ins.values(**r))
                    except IntegrityError:
                        pass  # idempotent
    except IntegrityError:
        # last-resort: ignore and continue (makes migration idempotent)
        pass


def _delete_rows(conn: Connection, table: Table, rows: Iterable[dict[str, Any]]):
    pk_cols = [c for c in table.primary_key.columns]
    if not pk_cols:
        return
    for r in rows:
        # Build WHERE on all PKs (supports composite)
        if all(col.name in r for col in pk_cols):
            cond = sa.and_(*[ (col == r[col.name]) for col in pk_cols ])
            conn.execute(sa.delete(table).where(cond))


def upgrade() -> None:
    conn: Connection = op.get_bind()
    insert_order, data = _load_seed()

    # Verify tables exist, and insert in declared order
    for name in insert_order:
        tbl = _reflect_table(conn, name)
        if tbl is None:
            # Table missing in this schema; skip
            op.get_context().impl.output(f"[seed] skip missing table: {name}")
            continue
        rows = data.get(name, [])
        if not rows:
            continue
        op.get_context().impl.output(f"[seed] inserting into {name}: {len(rows)} row(s)")
        _insert_rows(conn, tbl, rows)


def downgrade() -> None:
    conn: Connection = op.get_bind()
    insert_order, data = _load_seed()
    # Delete in reverse dependency order
    for name in reversed(insert_order):
        tbl = _reflect_table(conn, name)
        if tbl is None:
            continue
        rows = data.get(name, [])
        if not rows:
            continue
        op.get_context().impl.output(f"[seed] deleting from {name}: {len(rows)} row(s)")
        _delete_rows(conn, tbl, rows)