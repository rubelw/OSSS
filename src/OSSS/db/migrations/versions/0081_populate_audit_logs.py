# src/OSSS/db/migrations/versions/0081_populate_audit_logs.py
from __future__ import annotations

import os, csv, json, logging, uuid
from pathlib import Path
from contextlib import nullcontext
from typing import Optional

from alembic import op
import sqlalchemy as sa

# ---- Alembic identifiers ----
revision = "0081_populate_audit_logs"
down_revision = "0080_populate_agenda_itm_app"  # update if needed
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

# ---- Config / env toggles ----------------------------------------------------
LOG_LVL        = os.getenv("ALOG_LOG_LEVEL", "INFO").upper()
LOG_SQL        = os.getenv("ALOG_LOG_SQL", "1") == "1"
LOG_ROWS       = os.getenv("ALOG_LOG_ROWS", "1") == "1"
ABORT_IF_ZERO  = os.getenv("ALOG_ABORT_IF_ZERO", "1") == "1"

CSV_ENV        = "AUDIT_LOGS_CSV_PATH"   # dir or full file path
CSV_NAME       = "audit_logs.csv"

ALOGS_PER_ACTOR = int(os.getenv("ALOGS_PER_ACTOR", "1"))

# ---- Table names -------------------------------------------------------------
USERS_TBL   = "user_accounts"
TARGET_TBL  = "audit_logs"

# ---- Logging setup -----------------------------------------------------------
logging.getLogger("alembic.runtime.migration").setLevel(getattr(logging, LOG_LVL, logging.INFO))
_engine_logger = logging.getLogger("sqlalchemy.engine")
_engine_logger.setLevel(logging.INFO if LOG_SQL else getattr(logging, LOG_LVL, logging.INFO))


# ---- Helpers ----------------------------------------------------------------
def _outer_tx(conn):
    try:
        if hasattr(conn, "get_transaction") and conn.get_transaction() is not None:
            return nullcontext()
        if hasattr(conn, "in_transaction") and conn.in_transaction():
            return nullcontext()
    except Exception:
        return nullcontext()
    return conn.begin()


def _default_output_path(name: str) -> Path:
    envp = os.getenv(CSV_ENV)
    if envp:
        p = Path(envp)
        return (p / name) if p.is_dir() else p
    return Path(__file__).resolve().with_name(name)


def _uuid_sql(bind) -> str:
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


def _write_csv(bind) -> tuple[Path, int]:
    """
    Always (re)write audit_logs.csv using user_accounts.id for actor_id.
    """
    out = _default_output_path(CSV_NAME)
    out.parent.mkdir(parents=True, exist_ok=True)

    insp = sa.inspect(bind)
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["actor_id", "action", "entity_type", "entity_id", "metadata"])

        if not insp.has_table(USERS_TBL):
            log.warning("[%s] Table %s not found; wrote header-only CSV: %s", revision, USERS_TBL, out)
            return out, 0

        user_rows = bind.execute(sa.text(f"SELECT id FROM {USERS_TBL} ORDER BY id")).fetchall()
        user_ids = [str(r[0]) for r in user_rows]
        if not user_ids:
            log.warning("[%s] No users; wrote header-only CSV: %s", revision, out)
            return out, 0

        for uid in user_ids:
            for _ in range(max(1, ALOGS_PER_ACTOR)):
                meta = {
                    "seeded": True,
                    "seed_revision": revision,
                    "note": "Seeded AuditLog (alembic)"
                }
                # Write JSON **string** to CSV
                w.writerow([uid, "login", "user_account", uid, json.dumps(meta)])

    log.info("[%s] CSV generated with %d users => %s", revision, len(user_ids), out)
    return out, len(user_ids)


def _open_csv(csv_path: Path):
    f = csv_path.open("r", encoding="utf-8", newline="")
    reader = csv.DictReader(f)
    log.info("[%s] CSV headers: %s", revision, reader.fieldnames)
    try:
        from itertools import islice
        sample = list(islice(reader, 5))
        log.info("[%s] First rows preview: %s", revision, sample)
        f.seek(0); next(reader)
    except Exception:
        pass
    return reader, f


def _insert_sql(bind):
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns(TARGET_TBL)}

    insert_cols: list[str] = []
    select_vals: list[str] = []

    uuid_expr = _uuid_sql(bind)
    insert_cols.append("id")
    select_vals.append(uuid_expr if uuid_expr != ":_uuid" else ":_uuid")

    def add(col: str, val_sql: Optional[str] = None, param_name: Optional[str] = None):
        if col in cols:
            insert_cols.append(col)
            if val_sql is not None:
                select_vals.append(val_sql)
            else:
                select_vals.append(f":{param_name or col}")

    add("actor_id")
    add("action")
    add("entity_type")
    add("entity_id")

    # IMPORTANT: cast JSON string to JSONB on Postgres to avoid dict binding issues
    if bind.dialect.name == "postgresql":
        add("metadata", "CAST(:metadata AS JSONB)", "metadata")
    else:
        add("metadata", None, "metadata")  # best-effort for non-PG

    col_list   = ", ".join(insert_cols)
    values_sql = ", ".join(select_vals)

    # NOT EXISTS guard; includes metadata->>'seed_revision' on PG
    if bind.dialect.name == "postgresql":
        guard = (
            f" WHERE NOT EXISTS ("
            f"   SELECT 1 FROM {TARGET_TBL} t "
            f"   WHERE t.actor_id = :actor_id "
            f"     AND t.action = :action "
            f"     AND t.entity_type = :entity_type "
            f"     AND t.entity_id = :entity_id "
            f"     AND COALESCE(t.metadata->>'seed_revision','') = :seed_revision"
            f" )"
        )
    else:
        guard = (
            f" WHERE NOT EXISTS ("
            f"   SELECT 1 FROM {TARGET_TBL} t "
            f"   WHERE t.actor_id = :actor_id "
            f"     AND t.action = :action "
            f"     AND t.entity_type = :entity_type "
            f"     AND t.entity_id = :entity_id"
            f" )"
        )

    stmt = sa.text(
        f"INSERT INTO {TARGET_TBL} ({col_list}) "
        f"SELECT {values_sql}{guard}"
    )
    needs_uuid_param = (uuid_expr == ":_uuid")
    return stmt, cols, needs_uuid_param


# ---- Migration ---------------------------------------------------------------
def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if not insp.has_table(TARGET_TBL):
        log.info("[%s] Table %s missing; nothing to populate.", revision, TARGET_TBL)
        return

    csv_path, users_count = _write_csv(bind)
    reader, fobj = _open_csv(csv_path)

    insert_stmt, cols, needs_uuid_param = _insert_sql(bind)

    total = inserted = skipped = 0
    try:
        with _outer_tx(bind):
            for idx, raw in enumerate(reader, start=1):
                total += 1
                if not raw:
                    continue
                row = {
                    (k.strip() if isinstance(k, str) else k):
                    (v.strip() if isinstance(v, str) else v)
                    for k, v in raw.items()
                }

                actor_id    = row.get("actor_id") or None
                action      = row.get("action") or None
                entity_type = row.get("entity_type") or None
                entity_id   = row.get("entity_id") or None
                metadata_s  = row.get("metadata") or None   # keep as STRING

                if not (actor_id and action and entity_type and entity_id):
                    skipped += 1
                    if LOG_ROWS:
                        log.warning("[%s] row %d missing required fields — skipping: %r", revision, idx, row)
                    continue

                # We pass metadata as a JSON STRING (no json.loads), and CAST to JSONB in SQL.
                params = {
                    "actor_id": actor_id,
                    "action": action,
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "metadata": metadata_s,
                    "seed_revision": revision,  # used in guard
                }
                if needs_uuid_param:
                    params["_uuid"] = str(uuid.uuid4())

                # keep only known params (+ _uuid + seed_revision)
                params = {k: v for k, v in params.items() if (k in cols or k in {"_uuid", "seed_revision", "metadata"})}

                try:
                    bind.execute(insert_stmt, params)
                    inserted += 1
                    if LOG_ROWS:
                        log.info("[%s] row %d INSERT ok (actor_id=%s action=%s)", revision, idx, actor_id, action)
                except Exception:
                    skipped += 1
                    if LOG_ROWS:
                        log.exception("[%s] row %d INSERT failed; params=%r", revision, idx, params)
    finally:
        try:
            fobj.close()
        except Exception:
            pass

    log.info("[%s] CSV rows=%d, inserted=%d, skipped=%d (file=%s)",
             revision, total, inserted, skipped, csv_path)

    if ABORT_IF_ZERO and users_count > 0 and inserted == 0:
        raise RuntimeError(f"[{revision}] No rows inserted; set ALOG_LOG_ROWS=1 for per-row details.")


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not insp.has_table(TARGET_TBL):
        return
    try:
        if bind.dialect.name == "postgresql":
            res = bind.execute(sa.text(
                f"DELETE FROM {TARGET_TBL} WHERE metadata->>'seed_revision' = :rev"
            ), {"rev": revision})
        else:
            res = bind.execute(sa.text(
                f"DELETE FROM {TARGET_TBL} WHERE action='login' AND entity_type='user_account'"
            ))
        try:
            log.info("[%s] downgrade removed %s seeded rows from %s", revision, res.rowcount, TARGET_TBL)
        except Exception:
            pass
    except Exception:
        log.exception("[%s] downgrade best-effort delete failed", revision)