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
from sqlalchemy.exc import IntegrityError, ProgrammingError, DataError
from sqlalchemy.dialects.postgresql import insert as pg_insert

# add these near your other imports
from uuid import uuid4
from sqlalchemy.orm import Session

from datetime import datetime, date, timezone, time
from sqlalchemy.dialects.postgresql import UUID as PGUUID, TSVECTOR  # keep PGUUID; add TSVECTOR
from sqlalchemy.orm import Session


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

def _patch_missing_required(table: Table, row: dict[str, Any], session: Session) -> dict[str, Any]:
    out = dict(row)
    now = datetime.now(timezone.utc)

    # common timestamps (if schema has them)
    for ts in ("created_at", "updated_at"):
        if ts in table.c and out.get(ts) is None:
            out[ts] = now

    if table.name == "fiscal_periods":
        if out.get("year_number") is None:
            src = out.get("start_date") or out.get("end_date") or date.today()
            out["year_number"] = (src.year if isinstance(src, date) else date.today().year)
        out.setdefault("period_no", 1)
        out.setdefault("is_closed", False)

    if table.name == "periods":
        out.setdefault("start_time", time(8, 30, 0))
        out.setdefault("end_time", time(9, 15, 0))

    if table.name == "bus_stop_times":
        out.setdefault("arrival_time", time(7, 45, 0))

    if table.name == "orders":
        # supply a school_id if missing (use first school)
        if out.get("school_id") is None:
            sid = session.execute(sa.text("select id from schools limit 1")).scalar_one_or_none()
            if sid:
                out["school_id"] = sid
        out.setdefault("currency", "USD")
        out.setdefault("status", "PENDING")

    if table.name == "curricula":
        # safety: ensure organization_id exists or fallback to first org
        if out.get("organization_id") is None:
            oid = session.execute(sa.text("select id from mentors limit 1")).scalar_one_or_none()
            if oid:
                out["organization_id"] = oid

    return out

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

def _autofill_required_columns(table: Table, engine, session, row: dict[str, Any]) -> dict[str, Any]:
    """Fill in any NOT NULL, no-server-default columns that are missing/None using sample_for_column."""
    patched = dict(row)
    for col in table.columns:
        # Skip generated/computed columns
        if col.server_default is not None and getattr(col.server_default, "arg", None) is not None:
            continue
        need = (patched.get(col.name) is None) and (not col.nullable) and not getattr(col, "autoincrement", False)
        if need:
            val = sample_for_column(col, engine, session)
            if val != "__OMIT__" and val is not None:
                patched[col.name] = val

    # Per-table touch-ups (optional but handy)
    if table.name == "order_line_items" and "unit_price_cents" in [c.name for c in table.columns]:
        patched.setdefault("unit_price_cents", 100)

    return patched


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

def _coerce_time(value: Any) -> time | None:
    if value is None or isinstance(value, time):
        return value
    s = str(value).strip()
    # accept HH:MM[:SS]
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(s, fmt).time()
        except Exception:
            pass
    return None


def _filter_and_coerce_row(table: Table, row: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for col in table.columns:
        name = col.name
        if name not in row:
            continue
        val = row[name]

        # UUID
        is_uuid_col = False
        try:
            is_uuid_col = isinstance(col.type, PGUUID) or (getattr(col.type, "python_type", None) is uuid.UUID)
        except Exception:
            pass
        if is_uuid_col:
            out[name] = _coerce_uuid(val, table=str(table.name), column=name)
            continue

        # Datetime / Date / Time
        try:
            if isinstance(col.type, sa.DateTime):
                out[name] = _coerce_datetime(val)
                continue
            if isinstance(col.type, sa.Date):
                out[name] = _coerce_date(val)
                continue
            if isinstance(col.type, sa.Time):
                out[name] = _coerce_time(val)
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
                out[name] = _coerce_int(val)
                continue
        except Exception:
            pass

        # TSVECTOR: ignore whatever came from JSON; let DB compute
        try:
            if isinstance(col.type, TSVECTOR):
                continue
        except Exception:
            pass

        # String truncation to fit column length
        try:
            if isinstance(col.type, sa.String) and isinstance(val, str):
                n = getattr(col.type, "length", None)
                out[name] = val if not n or len(val) <= n else val[:n]
                continue
        except Exception:
            pass

        # default: pass through
        out[name] = val

    # Drop Nones for NOT NULL columns that also have server defaults
    for col in table.columns:
        if out.get(col.name) is None and not col.nullable and col.server_default is not None:
            out.pop(col.name, None)

    # ---- Per-table fallbacks for NOT NULL, no server default ----
    if table.name == "fiscal_periods":
        if out.get("year_number") is None:
            sd = out.get("start_date")
            out["year_number"] = sd.year if isinstance(sd, date) else datetime.now(timezone.utc).year
        if out.get("period_no") is None:
            out["period_no"] = 1

    if table.name == "periods":
        # supply sane defaults if missing
        if out.get("start_time") is None:
            out["start_time"] = time(8, 0)
        if out.get("end_time") is None:
            out["end_time"] = time(8, 45)

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

# ----- Synthetic sample row helpers ------------------------------------------

# in 0003_seed_tables.py

def sample_for_column(col, engine, session):
    name = col.name.lower()
    t = col.type

    # --- FKs: only RETURN an id; do not insert here ---
    if col.foreign_keys:
        fk = next(iter(col.foreign_keys))
        parent_tbl = fk.column.table
        parent_pk = fk.column

        # try to pick any existing parent id
        pid = session.execute(
            parent_tbl.select().with_only_columns(parent_pk).limit(1)
        ).scalar_one_or_none()

        if pid is not None:
            return pid

        # generate a plausible id of the correct type; real insert happens later
        from sqlalchemy.dialects.postgresql import UUID as PGUUID
        if isinstance(parent_pk.type, PGUUID):
            return uuid4()

        # numeric/other PKs
        from sqlalchemy import Integer, BigInteger, SmallInteger
        if isinstance(parent_pk.type, (Integer, BigInteger, SmallInteger)):
            return 1

        return None  # let later patchers handle if needed


def build_row(table, engine, session):
    row = {}
    for col in table.columns:
        # skip generated/server-default (e.g., tsvector computed)
        if col.server_default is not None and getattr(col.server_default, "arg", None) is not None:
            continue
        val = sample_for_column(col, engine, session)
        if val == "__OMIT__" or (val is None and col.nullable):
            continue
        row[col.name] = val
    # per-table tweaks
    if table.name == "order_line_items" and "unit_price_cents" in [c.name for c in table.columns]:
        row.setdefault("unit_price_cents", 100)
    return row


# add import near the top if not present
# import sqlalchemy as sa

def _ensure_fk_targets(session: Session, table: Table, row: dict[str, Any]) -> dict[str, Any]:
    """
    For each FK col in `table` that is present in `row`, ensure the referenced parent exists.
    If not, insert a minimal stub parent row.
    """
    conn = session.bind
    for col in table.columns:
        if not col.foreign_keys:
            continue
        if col.name not in row or row[col.name] is None:
            continue

        fk = next(iter(col.foreign_keys))
        parent_tbl = fk.column.table
        parent_pk = fk.column
        parent_id = row[col.name]

        has = session.execute(
            parent_tbl.select().with_only_columns(parent_pk).where(parent_pk == parent_id).limit(1)
        ).scalar_one_or_none()
        if has is not None:
            continue

        # build stub parent row: fill only *required* columns
        stub = {}
        for pcol in parent_tbl.columns:
            if pcol is parent_pk:
                stub[pcol.name] = parent_id
            elif pcol.nullable or pcol.server_default is not None or pcol.autoincrement:
                # let DB defaults / nullables handle themselves
                continue
            else:
                # primitive defaults by type/name; no recursive inserts here
                v = sample_for_column(pcol, conn, session)
                if v is None and str(pcol.type).lower().startswith("timestamp"):
                    v = datetime.now(timezone.utc)
                if v is None and pcol.name in ("name", "title"):
                    v = f"sample {parent_tbl.name}"
                if v is None and pcol.name in ("slug",):
                    v = "sample-" + parent_tbl.name.replace("_", "-")
                if v is None and str(pcol.type).lower().startswith("boolean"):
                    v = True
                stub[pcol.name] = v

        # Special case: mentors often have stricter NOT NULLs
        if parent_tbl.name == "mentors":
            stub.setdefault("name", "Sample Organization")
            stub.setdefault("slug", "sample-organization")
            stub.setdefault("created_at", datetime.now(timezone.utc))
            stub.setdefault("updated_at", datetime.now(timezone.utc))

        # insert inside a savepoint; ignore duplicates
        try:
            with conn.begin_nested():
                session.execute(parent_tbl.insert().values(**stub))
        except Exception:
            # if it races / violates, let it slide (someone else created it)
            pass

    return row

def upgrade() -> None:
    conn: Connection = op.get_bind()
    sess = Session(bind=conn)

    insert_order, data = _load_seed()

    for name in insert_order:
        tbl = _reflect_table(conn, name)
        if tbl is None:
            _emit(f"[seed] skip missing table: {name}")
            continue

        raw_rows = data.get(name, []) or []
        if not raw_rows:
            continue

        prepared = []
        for r in raw_rows:
            coerced = _filter_and_coerce_row(tbl, r)
            if not coerced:
                continue
            patched = _patch_missing_required(tbl, coerced, sess)
            ensured = _ensure_fk_targets(sess, tbl, patched)
            prepared.append(ensured)

        if not prepared:
            continue

        _emit(f"[seed] inserting into {name}: {len(prepared)} row(s)")

        # batch attempt in savepoint
        try:
            with conn.begin_nested():
                _insert_rows_batch(conn, tbl, prepared)
            continue
        except (IntegrityError, ProgrammingError, DataError) as e:
            _emit(f"[seed] batch insert failed for {name}: {e}; rolling back and retrying per-row")

        # per-row fallback
        for r in prepared:
            try:
                with conn.begin_nested():
                    _insert_row_single(conn, tbl, r)
            except (IntegrityError, ProgrammingError, DataError) as e:
                _emit(f"[seed] skipping row in {name}: {e}")


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
