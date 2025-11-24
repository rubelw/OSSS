from __future__ import annotations

import os
import uuid
from typing import Any, Dict, List
from datetime import datetime, date, time, timezone

from alembic import op, context
import sqlalchemy as sa
from sqlalchemy import MetaData, Table
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError, ProgrammingError, DataError
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.dialects import postgresql as psql

# ---- Alembic Identifiers ----
revision = "0003_seed_tables"
down_revision = "0002_add_tables"
depends_on = None

# ------------------------------------------------------------------------------
# CONFIG: DBML FILE LOCATIONS
# ------------------------------------------------------------------------------
CANDIDATE_DBML_PATHS = [
    os.getenv("SCHEMA_DBML_PATH"),
    os.path.join(os.path.dirname(__file__), "..", "schema.dbml"),
    os.path.join(os.path.dirname(__file__), "..", "..", "schema.dbml"),
]

# Tables we NEVER want placeholder rows for (pure index/join tables etc.)
PLACEHOLDER_SKIP_TABLES: set[str] = {
    "materials",
    "document_search_index",
    "policy_publications",
    "proposal_standard_map",
    "unit_standard_map",
}


def _emit(msg: str):
    try:
        context.config.print_stdout(msg)
    except Exception:
        print(msg)


# ------------------------------------------------------------------------------
# Minimal DBML Parser → Extract table names & rough order
# ------------------------------------------------------------------------------
def _load_dbml_tables() -> List[str]:
    path = next((p for p in CANDIDATE_DBML_PATHS if p and os.path.exists(p)), None)
    if not path:
        raise RuntimeError(
            "schema.dbml not found.\n"
            "Set SCHEMA_DBML_PATH or place schema.dbml in:\n"
            + "\n".join(f"  - {p}" for p in CANDIDATE_DBML_PATHS if p)
        )

    _emit(f"[seed] using DBML: {path}")

    tables: List[str] = []
    current = None
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if line.startswith("Table "):
                # E.g. Table users {  OR Table "users" {
                name = line.split()[1].strip('"`[]{}')
                current = name
                tables.append(name)
                continue
            if current and line.startswith("}"):
                current = None

    return tables


# ------------------------------------------------------------------------------
# Reflection + FK dependency graph
# ------------------------------------------------------------------------------
def _reflect_all(conn: Connection) -> Dict[str, Table]:
    md = MetaData()
    md.reflect(bind=conn)
    return dict(md.tables)


def _build_dep_graph(tables: Dict[str, Table]) -> Dict[str, set]:
    """
    Graph: table_name -> set of parent_table_names it depends on via FKs.
    """
    deps: Dict[str, set] = {name: set() for name in tables.keys()}
    for name, tbl in tables.items():
        parents = set()
        for fk in tbl.foreign_keys:
            parent_tbl = fk.column.table
            if parent_tbl is not None and parent_tbl.name in tables:
                parents.add(parent_tbl.name)
        deps[name] = parents
    return deps


def _toposort_tables(all_tables: Dict[str, Table], dbml_order: List[str]) -> List[str]:
    """
    Topologically sort tables using FK dependencies, but bias to DBML order
    for stability.
    """
    deps = _build_dep_graph(all_tables)
    # Compute reverse deps for Kahn
    dependents: Dict[str, set] = {name: set() for name in all_tables.keys()}
    for child, parents in deps.items():
        for p in parents:
            dependents.setdefault(p, set()).add(child)

    # In-degree
    indegree: Dict[str, int] = {name: len(parents) for name, parents in deps.items()}

    # Start queue with zero-dep nodes, ordered by dbml_order if present
    dbml_index = {name: i for i, name in enumerate(dbml_order)}
    queue = sorted(
        [n for n, d in indegree.items() if d == 0],
        key=lambda n: dbml_index.get(n, 10_000),
    )

    ordered: List[str] = []

    while queue:
        n = queue.pop(0)
        ordered.append(n)
        for child in dependents.get(n, set()):
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)
        queue.sort(key=lambda x: dbml_index.get(x, 10_000))

    # Any remaining nodes are in cycles; just append them in DBML-ish order
    remaining = [n for n, d in indegree.items() if d > 0 and n not in ordered]
    remaining.sort(key=lambda n: dbml_index.get(n, 10_000))
    ordered.extend(remaining)

    return ordered


# ------------------------------------------------------------------------------
# Type helpers
# ------------------------------------------------------------------------------
def _is_uuid_type(t: sa.types.TypeEngine) -> bool:
    try:
        if isinstance(t, PGUUID):
            return True
    except Exception:
        pass
    try:
        # Many UUID-ish types report python_type = uuid.UUID
        return getattr(t, "python_type", None) is uuid.UUID
    except NotImplementedError:
        return False
    except Exception:
        return False


def _coerce_uuid(value: Any, *, table: str, column: str):
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return value
    s = str(value).strip()
    try:
        return uuid.UUID(s)
    except Exception:
        return uuid.uuid5(uuid.NAMESPACE_URL, f"{table}.{column}:{s}")


def _coerce_datetime(value: Any):
    if value is None or isinstance(value, datetime):
        return value
    s = str(value).strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None


def _coerce_date(value: Any):
    if value is None or isinstance(value, date):
        return value
    s = str(value).split("T")[0]
    try:
        return date.fromisoformat(s)
    except Exception:
        return None


def _coerce_bool(value: Any):
    if value is None or isinstance(value, bool):
        return value
    s = str(value).strip().lower()
    if s in {"1", "true", "t", "yes", "y"}:
        return True
    if s in {"0", "false", "f", "no", "n"}:
        return False
    return None


def _coerce_int(value: Any):
    if value is None or isinstance(value, int):
        return value
    try:
        return int(str(value).strip())
    except Exception:
        return None


# ------------------------------------------------------------------------------
# Placeholder row builder (for tables with NO foreign keys)
# ------------------------------------------------------------------------------
def _make_placeholder_row(table: Table) -> dict[str, Any] | None:
    """
    Build a single 'safe-ish' placeholder row for a table
    that has *no foreign keys*.

    Assumption: caller has already ensured table.foreign_keys is empty.
    """
    now = datetime.now(timezone.utc)
    row: dict[str, Any] = {}

    for col in table.columns:
        name = col.name
        t = col.type

        # Let server defaults handle their own columns
        if col.server_default is not None:
            continue

        # Primary key
        if col.primary_key:
            if _is_uuid_type(t):
                row[name] = uuid.uuid5(uuid.NAMESPACE_URL, f"placeholder:{table.name}")
                continue
            if isinstance(t, (sa.Integer, sa.BigInteger, sa.SmallInteger)):
                row[name] = 1
                continue
            if isinstance(t, sa.String):
                length = getattr(t, "length", None)
                if length and length > 0:
                    base = (table.name[:length] or "x" * length)
                    row[name] = base[:length]
                else:
                    row[name] = f"{table.name}_pk"
                continue
            # fallback
            row[name] = f"{table.name}_pk"
            continue

        # Nullable? let it be NULL
        if col.nullable:
            row[name] = None
            continue

        # Non-nullable, type-based defaults
        if _is_uuid_type(t):
            row[name] = uuid.uuid5(
                uuid.NAMESPACE_URL, f"placeholder:{table.name}.{name}"
            )
            continue
        if isinstance(t, sa.Boolean):
            row[name] = False
            continue
        if isinstance(t, (sa.Integer, sa.BigInteger, sa.SmallInteger)):
            row[name] = 1
            continue
        if isinstance(t, (sa.Numeric, sa.Float, psql.DOUBLE_PRECISION)):
            row[name] = 0
            continue
        if isinstance(t, (sa.String, sa.Text)):
            row[name] = ""
            continue
        if isinstance(t, sa.Date):
            row[name] = date.today()
            continue
        if isinstance(t, sa.DateTime):
            row[name] = now
            continue
        if isinstance(t, sa.Time):
            row[name] = time(0, 0, 0)
            continue

        # Enums → pick first value, or bail out if none
        enum_types = (sa.Enum,)
        try:
            from sqlalchemy.dialects.postgresql import ENUM as PGEnum

            enum_types = (sa.Enum, PGEnum)
        except Exception:
            pass

        if isinstance(t, enum_types):
            enums = getattr(t, "enums", None) or getattr(t, "enum_values", None) or []
            if enums:
                row[name] = enums[0]
                continue
            _emit(
                f"[seed] table {table.name}: Enum column {name} has no values; skipping"
            )
            return None

        # JSON-ish
        try:
            from sqlalchemy.dialects.postgresql import JSONB, JSON

            if isinstance(t, (JSONB, JSON, sa.JSON)):
                row[name] = {}
                continue
        except Exception:
            if isinstance(t, sa.JSON):
                row[name] = {}
                continue

        # Fallback: NULL (if this hits a CHECK, we’ll log and skip)
        row[name] = None

    return row


def _filter_and_coerce_row(table: Table, row: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for col in table.columns:
        if col.name not in row:
            continue
        val = row[col.name]
        t = col.type

        if _is_uuid_type(t):
            out[col.name] = _coerce_uuid(val, table=str(table.name), column=col.name)
            continue

        if isinstance(t, sa.DateTime):
            out[col.name] = _coerce_datetime(val)
            continue

        if isinstance(t, sa.Date):
            out[col.name] = _coerce_date(val)
            continue

        if isinstance(t, sa.Boolean):
            coerced = _coerce_bool(val)
            out[col.name] = bool(coerced) if coerced is not None else None
            continue

        if isinstance(t, (sa.Integer, sa.BigInteger, sa.SmallInteger)):
            out[col.name] = _coerce_int(val)
            continue

        out[col.name] = val

    # allow server defaults to fill NOT NULL
    for col in table.columns:
        if out.get(col.name) is None and not col.nullable and col.server_default is not None:
            out.pop(col.name, None)

    return out


# ------------------------------------------------------------------------------
# Alembic Upgrade: DBML + FK-aware seeding
# ------------------------------------------------------------------------------
def upgrade() -> None:
    conn: Connection = op.get_bind()

    dbml_tables = _load_dbml_tables()
    all_reflected = _reflect_all(conn)

    # Filter to tables that exist in DB and are in DBML
    tables: Dict[str, Table] = {
        name: tbl for name, tbl in all_reflected.items() if name in dbml_tables
    }

    if not tables:
        _emit("[seed] no tables found to seed (DBML vs DB mismatch?)")
        return

    order = _toposort_tables(tables, dbml_tables)
    _emit(f"[seed] final FK-aware table order: {order}")

    for name in order:
        tbl = tables[name]

        # Skip explicit no-placeholder tables
        if name in PLACEHOLDER_SKIP_TABLES:
            _emit(f"[seed] table {name}: in placeholder skip list; skipping")
            continue

        # 🚨 NEW: don't seed tables with any foreign keys
        if tbl.foreign_keys:
            _emit(f"[seed] table {name}: has foreign keys; skipping placeholder for this table")
            continue

        placeholder = _make_placeholder_row(tbl)
        if placeholder is None:
            _emit(f"[seed] table {name}: could not build placeholder row; skipping")
            continue

        prepared = _filter_and_coerce_row(tbl, placeholder)

        _emit(f"[seed] inserting placeholder row into {name}")

        try:
            with conn.begin_nested():
                pk_cols = [c for c in tbl.primary_key.columns]
                if conn.dialect.name == "postgresql" and pk_cols:
                    stmt = (
                        pg_insert(tbl)
                        .values(prepared)
                        .on_conflict_do_nothing(index_elements=[c.name for c in pk_cols])
                    )
                else:
                    stmt = sa.insert(tbl).values(**prepared)

                conn.execute(stmt)

        except (IntegrityError, ProgrammingError, DataError) as e:
            _emit(f"[seed] failed for {name}: {e!r}")


# ------------------------------------------------------------------------------
# Downgrade: wipe all seeded rows (simple strategy)
# ------------------------------------------------------------------------------
def downgrade() -> None:
    conn: Connection = op.get_bind()
    dbml_tables = _load_dbml_tables()
    all_reflected = _reflect_all(conn)
    tables: Dict[str, Table] = {
        name: tbl for name, tbl in all_reflected.items() if name in dbml_tables
    }

    order = _toposort_tables(tables, dbml_tables)
    for name in reversed(order):
        tbl = tables[name]
        _emit(f"[seed] clearing table {name}")
        conn.execute(sa.delete(tbl))
