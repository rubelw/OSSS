from __future__ import annotations

import csv
import logging
import os
import random
import uuid
from datetime import datetime, timezone
from typing import List, Dict

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert  # used on PG when available

# ---- Alembic identifiers ----
revision = "0097_seed_subscriptions"
down_revision = "0096_seed_channels"  # update if needed
branch_labels = None
depends_on = None

# ---- Logging ---------------------------------------------------------------
log = logging.getLogger("alembic.runtime.migration")

# --- Config knobs ---
CSV_FILENAME = "subscriptions.csv"
DEFAULT_ROW_COUNT = int(os.getenv("SUBSCRIPTION_ROWS", "1500"))
SEED = os.getenv("SUBSCRIPTION_SEED")  # e.g. "42"
DEFAULT_TYPE_WEIGHTS = {"user": 0.75, "group": 0.20, "role": 0.05}

STAGING = "subscriptions_import"
SUBS_TABLE = "subscriptions"
CHAN_TABLE = "channels"


# --- Helpers -------------------------------------------------------------------
def _sync_version_table(bind: sa.engine.Connection, expected_prev: str, this_rev: str) -> None:
    """
    Ensure the alembic_version table has exactly one row that equals `expected_prev`
    so Alembic's end-of-migration UPDATE matches 1 row.

    Handles cases:
      - table missing  -> noop
      - table empty    -> INSERT expected_prev
      - single wrong   -> UPDATE that single value to expected_prev
      - already this_rev -> flip back to expected_prev (so Alembic can UPDATE to this_rev)
      - multi-row (branching) -> leave as-is (don't guess)
    """
    insp = sa.inspect(bind)
    if not insp.has_table("alembic_version"):
        return

    vals = [r[0] for r in bind.execute(sa.text("SELECT version_num FROM alembic_version")).fetchall()]
    if not vals:
        bind.execute(
            sa.text("INSERT INTO alembic_version (version_num) VALUES (:v)"),
            {"v": expected_prev},
        )
        log.warning("[subscriptions] alembic_version was empty; inserted bootstrap row '%s'", expected_prev)
        return

    if len(vals) == 1:
        cur = vals[0]
        if cur == expected_prev:
            return
        # If it's already at this migration's revision, flip back so Alembic's UPDATE will match.
        bind.execute(
            sa.text("UPDATE alembic_version SET version_num=:new WHERE version_num=:old"),
            {"new": expected_prev, "old": cur},
        )
        log.warning("[subscriptions] alembic_version was '%s'; set to '%s' for consistent upgrade.", cur, expected_prev)
        return

    # Multiple rows (branches) -> don't auto-mutate; let Alembic manage branches explicitly.
    log.warning("[subscriptions] alembic_version has multiple rows (%s); leaving as-is.", len(vals))


def _csv_path() -> str:
    return os.path.join(os.path.dirname(__file__), CSV_FILENAME)

def _fetch_all_scalar(conn, sql: str) -> List[str]:
    return [r[0] for r in conn.execute(sa.text(sql)).fetchall()]

def _table_exists(conn, table_name: str) -> bool:
    try:
        conn.execute(sa.text(f"SELECT 1 FROM {table_name} LIMIT 1"))
        return True
    except Exception:
        return False

def _fetch_reference_data(conn):
    channels = _fetch_all_scalar(conn, f"SELECT id FROM {CHAN_TABLE}")
    if not channels:
        raise RuntimeError("No channels found. Cannot populate subscriptions.")

    principals: Dict[str, List[str]] = {}

    if _table_exists(conn, "users"):
        users = _fetch_all_scalar(conn, "SELECT id FROM users")
        if users:
            principals["user"] = users

    if _table_exists(conn, "groups"):
        groups = _fetch_all_scalar(conn, "SELECT id FROM groups")
        if groups:
            principals["group"] = groups

    if _table_exists(conn, "roles"):
        roles = _fetch_all_scalar(conn, "SELECT id FROM roles")
        if roles:
            principals["role"] = roles

    if not principals:
        raise RuntimeError(
            "No principals found. Expected one or more of (users, groups, roles) tables to contain rows."
        )

    return channels, principals

def _choose_type(weights: Dict[str, float]) -> str:
    total = sum(weights.values())
    r = random.random() * total
    acc = 0.0
    for t, w in weights.items():
        acc += w
        if r <= acc:
            return t
    return next(iter(weights.keys()))

def _normalize_weights(avail_types: List[str]) -> Dict[str, float]:
    subset = {k: v for k, v in DEFAULT_TYPE_WEIGHTS.items() if k in avail_types}
    if not subset:
        return {avail_types[0]: 1.0}
    s = sum(subset.values())
    return {k: (v / s if s else 1.0 / len(subset)) for k, v in subset.items()}

def _generate_rows(
    channel_ids: List[str],
    principals: Dict[str, List[str]],
    max_rows: int,
) -> List[Dict[str, object]]:
    if SEED is not None:
        try:
            random.seed(int(SEED))
        except ValueError:
            random.seed(SEED)

    if not channel_ids:
        raise RuntimeError("No channels to subscribe against.")
    avail_types = sorted(principals.keys())
    weights = _normalize_weights(avail_types)

    total_principals = sum(len(principals[t]) for t in avail_types)
    theoretical_max = len(channel_ids) * total_principals
    target = min(max_rows, theoretical_max)

    unique = set()
    rows: List[Dict[str, object]] = []
    now = datetime.now(timezone.utc).isoformat()

    log.info(
        "[subscriptions] generating rows; channels=%d, principals={%s}, target=%d (cap=%d)",
        len(channel_ids),
        ", ".join(f"{t}:{len(principals[t])}" for t in avail_types),
        target,
        theoretical_max,
    )

    attempts = 0
    max_attempts = target * 10 if target else 1000

    while len(rows) < target and attempts < max_attempts:
        attempts += 1
        ch = random.choice(channel_ids)
        ptype = _choose_type(weights)
        pid = random.choice(principals[ptype])

        key = (ch, ptype, pid)
        if key in unique:
            continue
        unique.add(key)

        rows.append(
            {
                "id": str(uuid.uuid4()),
                "channel_id": ch,
                "principal_type": ptype,
                "principal_id": pid,
                "created_at": now,
            }
        )

    if len(rows) < target:
        log.warning(
            "[subscriptions] generated %d rows < target=%d (uniqueness/data limits).",
            len(rows),
            target,
        )
    else:
        log.info("[subscriptions] generated %d rows.", len(rows))

    return rows

def _write_csv(csv_path: str, rows: List[Dict[str, object]]) -> None:
    fieldnames = ["id", "channel_id", "principal_type", "principal_id", "created_at"]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    log.info("[subscriptions] wrote CSV: %s (rows=%d)", csv_path, len(rows))

def _read_csv(csv_path: str) -> List[Dict[str, object]]:
    with open(csv_path, "r", newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        data = list(r)
    log.info("[subscriptions] read CSV: %s (rows=%d)", csv_path, len(data))
    return data

def _uuid_sql(bind: sa.engine.Connection) -> str:
    if bind.dialect.name != "postgresql":
        return ":_uuid"
    try:
        bind.execute(sa.text("SELECT gen_random_uuid()"))
        return "gen_random_uuid()"
    except Exception:
        pass
    try:
        bind.execute(sa.text("SELECT uuid_generate_v4()"))
        return "uuid_generate_v4()"
    except Exception:
        pass
    return ":_uuid"

def _reset_failed_tx(bind: sa.engine.Connection) -> None:
    """If the connection is in an aborted transaction, issue a ROLLBACK so subsequent DDL can run."""
    try:
        bind.execute(sa.text("SELECT 1"))
    except Exception:
        try:
            bind.exec_driver_sql("ROLLBACK")
            log.warning("[subscriptions] detected aborted transaction; issued ROLLBACK")
        except Exception:
            log.exception("[subscriptions] failed to ROLLBACK an aborted transaction")

def _ensure_prev_version_row(bind: sa.engine.Connection, expected_prev: str) -> None:
    """
    If the alembic_version table exists but is empty (common in partial reseeds),
    insert the expected down_revision so Alembic's version UPDATE at the end
    matches exactly one row instead of 0.
    """
    try:
        insp = sa.inspect(bind)
        if not insp.has_table("alembic_version"):
            return
        cnt = bind.execute(sa.text("SELECT COUNT(*) FROM alembic_version")).scalar()
        if cnt == 0:
            bind.execute(
                sa.text("INSERT INTO alembic_version (version_num) VALUES (:v)"),
                {"v": expected_prev},
            )
            log.warning(
                "[subscriptions] alembic_version was empty; inserted bootstrap row '%s'",
                expected_prev,
            )
    except Exception as e:
        log.warning("[subscriptions] could not ensure alembic_version row: %s", e)


# --- Migration ops -------------------------------------------------------------

def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)

    # Make sure the version table will let Alembic's final UPDATE match exactly one row
    _sync_version_table(bind, expected_prev=down_revision, this_rev=revision)

    # Ensure alembic_version has the expected previous revision when table is empty
    _ensure_prev_version_row(bind, down_revision)

    # 1) Reference data
    channel_ids, principals = _fetch_reference_data(bind)

    # 2) Generate + write CSV
    rows = _generate_rows(channel_ids, principals, DEFAULT_ROW_COUNT)
    csv_path = _csv_path()
    _write_csv(csv_path, rows)

    # 3) Recreate staging table (no autocommit block; ensure clean txn first)
    _reset_failed_tx(bind)
    try:
        op.execute(sa.text(f"DROP TABLE IF EXISTS {STAGING}"))
    except Exception:
        pass

    op.create_table(
        STAGING,
        sa.Column("id", sa.Text, nullable=True),
        sa.Column("channel_id", sa.Text, nullable=False),
        sa.Column("principal_type", sa.Text, nullable=False),
        sa.Column("principal_id", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )

    meta = sa.MetaData()
    imp = sa.Table(STAGING, meta, autoload_with=bind)

    # 4) Load CSV into staging
    data = _read_csv(csv_path)
    staged = []
    for r in data:
        try:
            created = (r.get("created_at") or "").strip()
            created_dt = datetime.fromisoformat(created.replace("Z", "")) if created else None
        except Exception:
            created_dt = None

        staged.append(
            {
                "id": (r.get("id") or "").strip() or None,
                "channel_id": (r.get("channel_id") or "").strip(),
                "principal_type": (r.get("principal_type") or "").strip() or "user",
                "principal_id": (r.get("principal_id") or "").strip(),
                "created_at": created_dt,
            }
        )

    if staged:
        bind.execute(sa.insert(imp), staged)
    else:
        log.info("[subscriptions] staging empty; nothing to insert.")
        try:
            op.execute(sa.text(f"DROP TABLE IF EXISTS {STAGING}"))
        except Exception:
            pass
        return

    # 5) Reflect targets and build INSERT … SELECT … JOIN channels (FK-safe)
    subs = sa.Table(SUBS_TABLE, meta, autoload_with=bind)
    chans = sa.Table(CHAN_TABLE, meta, autoload_with=bind)

    subs_cols = {c.name: c for c in subs.c}
    chan_id_col = chans.c["id"]
    sub_chan_col = subs_cols["channel_id"]
    sub_pid_col = subs_cols["principal_id"]

    uuid_expr = _uuid_sql(bind)

    select_cols = []
    ins_cols = []

    if "id" in subs_cols:
        id_type = subs_cols["id"].type
        if uuid_expr == ":_uuid":
            uuid_param = sa.bindparam("_uuid", type_=id_type)
            id_fallback = uuid_param
        else:
            id_fallback = sa.text(uuid_expr)
        id_expr = sa.func.coalesce(
            sa.cast(sa.func.nullif(imp.c.id, ""), id_type),
            sa.cast(id_fallback, id_type) if isinstance(id_fallback, sa.BindParameter) else id_fallback,
        ).label("id")
        select_cols.append(id_expr); ins_cols.append("id")

    select_cols.append(sa.cast(chans.c.id, sub_chan_col.type).label("channel_id")); ins_cols.append("channel_id")
    select_cols.append(imp.c.principal_type.label("principal_type")); ins_cols.append("principal_type")
    select_cols.append(sa.cast(imp.c.principal_id, sub_pid_col.type).label("principal_id")); ins_cols.append("principal_id")

    if "created_at" in subs_cols:
        select_cols.append(sa.func.coalesce(imp.c.created_at, sa.func.now()).label("created_at")); ins_cols.append("created_at")
    if "updated_at" in subs_cols:
        select_cols.append(sa.func.now().label("updated_at")); ins_cols.append("updated_at")

    join_cond = (chan_id_col == sa.cast(imp.c.channel_id, chan_id_col.type))
    select_src = sa.select(*select_cols).select_from(imp.join(chans, join_cond))

    # 6) Clear target table (fresh reseed) — stay inside Alembic txn
    op.execute(sa.text(f"TRUNCATE TABLE {SUBS_TABLE} RESTART IDENTITY CASCADE"))

    # 7) Insert with idempotency
    uq_cols = None
    try:
        for u in insp.get_unique_constraints(SUBS_TABLE):
            cols = u.get("column_names") or []
            if set(cols) == {"channel_id", "principal_type", "principal_id"}:
                uq_cols = cols
                break
    except Exception:
        pass

    if bind.dialect.name == "postgresql" and uq_cols:
        stmt = pg_insert(subs).from_select(ins_cols, select_src).on_conflict_do_nothing(
            index_elements=uq_cols
        )
        params = {}
        if "id" in subs_cols and uuid_expr == ":_uuid":
            params["_uuid"] = str(uuid.uuid4())
        bind.execute(stmt, params or None)
    else:
        compiled = select_src.compile(bind, compile_kwargs={"literal_binds": True})
        sql = sa.text(
            f"INSERT INTO {SUBS_TABLE} ({', '.join(ins_cols)}) "
            f"SELECT * FROM ({compiled}) AS src "
            f"WHERE NOT EXISTS ("
            f"  SELECT 1 FROM {SUBS_TABLE} t "
            f"  WHERE t.channel_id = src.channel_id "
            f"    AND t.principal_type = src.principal_type "
            f"    AND t.principal_id = src.principal_id)"
        )
        bind.execute(sql)

    # 8) Cleanup staging (still within the migration txn)
    try:
        op.execute(sa.text(f"DROP TABLE IF EXISTS {STAGING}"))
    except Exception:
        pass

    log.info("[subscriptions] finished inserting rows into %s.", SUBS_TABLE)


def downgrade() -> None:
    bind = op.get_bind()
    log.info("[subscriptions] clearing table with TRUNCATE CASCADE")
    op.execute(sa.text(f"TRUNCATE TABLE {SUBS_TABLE} RESTART IDENTITY CASCADE"))
