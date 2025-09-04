# src/OSSS/db/migrations/versions/0081_populate_audit_logs.py
from __future__ import annotations

import os, csv, json, logging, uuid, random
from pathlib import Path
from contextlib import nullcontext
from typing import Optional

from alembic import op
import sqlalchemy as sa

# ---- Alembic identifiers ----
revision = "0085_populate_approvals"
down_revision = "0084_populate_alignments"  # update if needed
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

# ---- Config / env toggles ----------------------------------------------------
LOG_LVL        = os.getenv("APR_LOG_LEVEL", "DEBUG").upper()
LOG_SQL        = os.getenv("APR_LOG_SQL", "1") == "1"
LOG_ROWS       = os.getenv("APR_LOG_ROWS", "1") == "1"
ABORT_IF_ZERO  = os.getenv("APR_ABORT_IF_ZERO", "1") == "1"

CSV_ENV        = "APPROVALS_CSV_PATH"
CSV_NAME       = "approvals.csv"

APR_PER_PROPOSAL = int(os.getenv("APR_PER_PROPOSAL", "1"))      # approvals per proposal
APR_STATUS       = os.getenv("APR_STATUS", "active")            # default status to seed
APR_SEED         = os.getenv("APR_SEED")                        # set for deterministic picks

# ---- Table names -------------------------------------------------------------
PROPOSALS_TBL   = "proposals"
ASSOCS_TBL      = "education_associations"   # change if your table is actually named "associations"
APPROVALS_TBL   = "approvals"

# ---- Logging setup -----------------------------------------------------------
logging.getLogger("alembic.runtime.migration").setLevel(getattr(logging, LOG_LVL, logging.INFO))
_engine_logger = logging.getLogger("sqlalchemy.engine")
_engine_logger.setLevel(logging.INFO if LOG_SQL else getattr(logging, LOG_LVL, logging.INFO))


# ---- Helper logging ----------------------------------------------------------
def _log_env(bind: sa.engine.Connection) -> None:
    try:
        log.info(
            "[%s] cfg: LOG_LVL=%s LOG_SQL=%s LOG_ROWS=%s ABORT_IF_ZERO=%s CSV_ENV=%s APR_PER_PROPOSAL=%s APR_STATUS=%s APR_SEED=%s",
            revision, LOG_LVL, LOG_SQL, LOG_ROWS, ABORT_IF_ZERO, os.getenv(CSV_ENV), APR_PER_PROPOSAL, APR_STATUS, APR_SEED
        )
        log.info(
            "[%s] using tables: proposals=%s associations=%s approvals=%s (dialect=%s)",
            revision, PROPOSALS_TBL, ASSOCS_TBL, APPROVALS_TBL, bind.dialect.name
        )
    except Exception:
        pass


def _outer_tx(conn):
    """Open a transaction only if one isn't already active."""
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
        out = (p / name) if p.is_dir() else p
    else:
        out = Path(__file__).resolve().with_name(name)
    log.info("[%s] CSV path resolved to: %s", revision, out)
    return out


def _uuid_sql(bind) -> str:
    """Prefer gen_random_uuid(), fall back to uuid_generate_v4(), else parameterize."""
    if bind.dialect.name != "postgresql":
        log.debug("[%s] non-PostgreSQL dialect; will parametrize UUID as :_uuid", revision)
        return ":_uuid"
    try:
        bind.execute(sa.text("SELECT gen_random_uuid()"))
        log.debug("[%s] using gen_random_uuid() for id", revision)
        return "gen_random_uuid()"
    except Exception:
        log.debug("[%s] gen_random_uuid() not available", revision)
    try:
        bind.execute(sa.text("SELECT uuid_generate_v4()"))
        log.debug("[%s] using uuid_generate_v4() for id", revision)
        return "uuid_generate_v4()"
    except Exception:
        log.debug("[%s] uuid_generate_v4() not available; will parametrize UUID as :_uuid", revision)
    return ":_uuid"


def _ensure_schema(bind):
    """
    Ensure the unique constraint (proposal_id, association_id) exists for ON CONFLICT.
    **Only** attempt to create it if both columns exist, to avoid aborting the transaction.
    """
    insp = sa.inspect(bind)
    if not insp.has_table(APPROVALS_TBL):
        log.warning("[%s] table %s does not exist; skipping schema ensure", revision, APPROVALS_TBL)
        return

    try:
        cols = {c["name"] for c in insp.get_columns(APPROVALS_TBL)}
    except Exception:
        log.warning("[%s] approvals columns not introspectable; skipping schema ensure.", revision)
        return

    expected_cols = ("proposal_id", "association_id")
    missing = [c for c in expected_cols if c not in cols]
    if missing:
        log.info("[%s] skipping unique constraint on %s — missing columns: %s",
                 revision, APPROVALS_TBL, ", ".join(missing))
        return  # Do NOT attempt DDL that would fail and poison the txn.

    # At this point both columns exist; check current unique constraints
    try:
        uqs = insp.get_unique_constraints(APPROVALS_TBL)
    except Exception:
        uqs = []

    # Already have an equivalent constraint?
    for uc in uqs:
        names = uc.get("column_names") or []
        if set(names) == set(expected_cols):
            log.info("[%s] unique constraint on (%s) already present on %s; skipping.",
                     revision, ", ".join(expected_cols), APPROVALS_TBL)
            return

    # Safe to create
    try:
        op.create_unique_constraint("uq_approval_proposal_assoc", APPROVALS_TBL, list(expected_cols))
        log.info("[%s] created unique constraint uq_approval_proposal_assoc on (%s)",
                 revision, ", ".join(expected_cols))
    except Exception:
        log.exception("[%s] create_unique_constraint failed (non-fatal)", revision)


def _write_csv(bind) -> tuple[Path, int]:
    """
    (Re)generate approvals.csv from current proposals and associations.
    Returns (path, number_of_rows_written).
    """
    out = _default_output_path(CSV_NAME)
    out.parent.mkdir(parents=True, exist_ok=True)

    insp = sa.inspect(bind)
    have_props = insp.has_table(PROPOSALS_TBL)
    have_assocs = insp.has_table(ASSOCS_TBL)
    log.info("[%s] table existence: %s=%s, %s=%s", revision, PROPOSALS_TBL, have_props, ASSOCS_TBL, have_assocs)

    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["proposal_id", "association_id", "status", "expires_at"])

        if not (have_props and have_assocs):
            log.warning("[%s] Missing %s or %s; wrote header-only CSV: %s",
                        revision, PROPOSALS_TBL, ASSOCS_TBL, out)
            return out, 0

        prop_ids = [str(r[0]) for r in bind.execute(sa.text(f"SELECT id FROM {PROPOSALS_TBL} ORDER BY id")).fetchall()]
        assoc_ids = [str(r[0]) for r in bind.execute(sa.text(f"SELECT id FROM {ASSOCS_TBL} ORDER BY id")).fetchall()]
        log.info("[%s] found %d proposals and %d associations", revision, len(prop_ids), len(assoc_ids))

        if not prop_ids or not assoc_ids or APR_PER_PROPOSAL <= 0:
            log.info("[%s] Nothing to seed (props=%d, assocs=%d, per_proposal=%d); header-only CSV written: %s",
                     revision, len(prop_ids), len(assoc_ids), APR_PER_PROPOSAL, out)
            return out, 0

        rng = random.Random(APR_SEED)
        rows = 0
        for pid in prop_ids:
            if len(assoc_ids) >= APR_PER_PROPOSAL:
                chosen = rng.sample(assoc_ids, APR_PER_PROPOSAL)
            else:
                chosen = [assoc_ids[i % len(assoc_ids)] for i in range(APR_PER_PROPOSAL)]
            log.debug("[%s] proposal %s -> associations chosen: %s", revision, pid, chosen)
            for aid in chosen:
                status = APR_STATUS
                expires_at = ""      # empty => NULL
                w.writerow([pid, aid, status, expires_at])
                rows += 1

    log.info("[%s] CSV generated with %d rows => %s", revision, rows, out)
    return out, rows


def _open_csv(csv_path: Path):
    f = csv_path.open("r", encoding="utf-8", newline="")
    reader = csv.DictReader(f)
    try:
        from itertools import islice
        sample = list(islice(reader, 5))
        log.info("[%s] CSV headers: %s; first rows preview: %s", revision, reader.fieldnames, sample)
        f.seek(0); next(reader)  # rewind to first data row
    except Exception:
        log.exception("[%s] could not preview CSV", revision)
    return reader, f


def _insert_sql(bind):
    """
    Build INSERT for approvals. If a unique (proposal_id, association_id) exists,
    use ON CONFLICT DO NOTHING; otherwise use SELECT … WHERE NOT EXISTS guard.
    """
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns(APPROVALS_TBL)}
    log.info("[%s] %s columns: %s", revision, APPROVALS_TBL, sorted(cols))

    ins_cols, vals = [], []

    uuid_expr = _uuid_sql(bind)
    if "id" in cols:
        ins_cols.append("id")
        vals.append(uuid_expr if uuid_expr != ":_uuid" else ":_uuid")

    def add(col: str, param: Optional[str] = None):
        if col in cols:
            ins_cols.append(col)
            vals.append(f":{param or col}")

    add("proposal_id")
    add("association_id")
    add("expires_at")  # nullable
    add("status")      # server default exists, but we allow explicit

    cols_sql = ", ".join(ins_cols)

    # Detect constraint for ON CONFLICT
    uqs = {u["name"]: u for u in insp.get_unique_constraints(APPROVALS_TBL)}
    log.info("[%s] unique constraints on %s: %s", revision, APPROVALS_TBL, {k: v.get("column_names") for k, v in uqs.items()})
    uq_name = None
    for name, meta in uqs.items():
        if set(meta.get("column_names") or []) == {"proposal_id", "association_id"}:
            uq_name = name
            break

    if bind.dialect.name == "postgresql" and uq_name:
        sql = sa.text(
            f"INSERT INTO {APPROVALS_TBL} ({cols_sql}) VALUES ({', '.join(vals)}) "
            f"ON CONFLICT ON CONSTRAINT {uq_name} DO NOTHING"
        )
        log.info("[%s] using ON CONFLICT path with constraint %s", revision, uq_name)
        log.debug("[%s] SQL:\n%s", revision, sql.text)
        needs_uuid_param = (uuid_expr == ":_uuid")
    else:
        # Portable guard: INSERT … SELECT … WHERE NOT EXISTS …
        select_list = ", ".join(vals)
        guard = (
            f" WHERE NOT EXISTS (SELECT 1 FROM {APPROVALS_TBL} t "
            f"WHERE t.proposal_id = :proposal_id AND t.association_id = :association_id)"
        )
        sql = sa.text(
            f"INSERT INTO {APPROVALS_TBL} ({cols_sql}) SELECT {select_list}{guard}"
        )
        log.info("[%s] using WHERE NOT EXISTS guard path", revision)
        log.debug("[%s] SQL:\n%s", revision, sql.text)
        needs_uuid_param = (uuid_expr == ":_uuid")

    return sql, cols, needs_uuid_param


# ---- Migration ---------------------------------------------------------------
def upgrade() -> None:
    bind = op.get_bind()
    _log_env(bind)

    insp = sa.inspect(bind)
    log.info("[%s] has_table(%s)=%s, has_table(%s)=%s, has_table(%s)=%s",
             revision,
             PROPOSALS_TBL, insp.has_table(PROPOSALS_TBL),
             ASSOCS_TBL,    insp.has_table(ASSOCS_TBL),
             APPROVALS_TBL, insp.has_table(APPROVALS_TBL))

    # Ensure schema only if columns actually exist (prevents txn aborts)
    _ensure_schema(bind)

    # If approvals table is missing required columns, don’t attempt inserts.
    if not insp.has_table(APPROVALS_TBL):
        log.info("[%s] Table %s missing; nothing to populate.", revision, APPROVALS_TBL)
        return
    try:
        a_cols = {c["name"] for c in insp.get_columns(APPROVALS_TBL)}
    except Exception:
        a_cols = set()
    if not {"proposal_id", "association_id"}.issubset(a_cols):
        log.info("[%s] %s lacks required columns (have=%s); skipping data insert.", revision, APPROVALS_TBL, sorted(a_cols))
        # Still write a header-only CSV (useful for ops visibility)
        _write_csv(bind)
        return

    # Show counts ahead of CSV
    try:
        if insp.has_table(PROPOSALS_TBL):
            pc = bind.execute(sa.text(f"SELECT count(*) FROM {PROPOSALS_TBL}")).scalar() or 0
            log.info("[%s] proposal rows available: %s", revision, pc)
        if insp.has_table(ASSOCS_TBL):
            ac = bind.execute(sa.text(f"SELECT count(*) FROM {ASSOCS_TBL}")).scalar() or 0
            log.info("[%s] association rows available: %s", revision, ac)
    except Exception:
        log.exception("[%s] failed to count proposals/associations", revision)

    csv_path, csv_rows = _write_csv(bind)
    reader, fobj = _open_csv(csv_path)

    insert_stmt, cols, needs_uuid_param = _insert_sql(bind)

    total = inserted = skipped = 0
    try:
        with _outer_tx(bind):
            for idx, raw in enumerate(reader, start=1):
                total += 1
                if not raw:
                    continue
                row = { (k.strip() if isinstance(k, str) else k): (v.strip() if isinstance(v, str) else v)
                        for k, v in raw.items() }
                if LOG_ROWS:
                    log.debug("[%s] row %d raw: %r", revision, idx, row)

                pid   = row.get("proposal_id") or None
                aid   = row.get("association_id") or None
                status = row.get("status") or APR_STATUS or None
                expires_at = row.get("expires_at") or None
                if expires_at in ("", "null", "NULL"):
                    expires_at = None

                if not pid or not aid:
                    skipped += 1
                    if LOG_ROWS:
                        log.warning("[%s] row %d missing proposal_id/association_id — skipping: %r",
                                    revision, idx, row)
                    continue

                params = {
                    "proposal_id": pid,
                    "association_id": aid,
                    "status": status,
                    "expires_at": expires_at,
                }
                if needs_uuid_param and "id" in cols:
                    import uuid as _uuid
                    params["_uuid"] = str(_uuid.uuid4())

                # Keep only params that are real columns (+ _uuid)
                before = params.copy()
                params = {k: v for k, v in params.items() if (k in cols or k == "_uuid")}
                if LOG_ROWS and before != params:
                    log.debug("[%s] row %d pruned params: before=%r after=%r (cols=%s)", revision, idx, before, params, cols)

                try:
                    if LOG_ROWS:
                        log.debug("[%s] executing INSERT for row %d with params=%r", revision, idx, params)
                    bind.execute(insert_stmt, params)
                    inserted += 1
                    if LOG_ROWS:
                        log.info("[%s] row %d INSERT ok (proposal=%s, association=%s)",
                                 revision, idx, pid, aid)
                except Exception:
                    skipped += 1
                    log.exception("[%s] row %d INSERT failed; params=%r", revision, idx, params)

    finally:
        try:
            fobj.close()
        except Exception:
            pass

    log.info("[%s] CSV rows=%d, attempted=%d, inserted=%d, skipped=%d (file=%s)",
             revision, csv_rows, total, inserted, skipped, csv_path)

    if ABORT_IF_ZERO and csv_rows > 0 and inserted == 0:
        log.error("[%s] zero rows inserted but CSV had %d rows; set APR_LOG_ROWS=1 for per-row details.", revision, csv_rows)
        raise RuntimeError(f"[{revision}] No rows inserted; set APR_LOG_ROWS=1 for per-row details.")


def downgrade() -> None:
    """
    Best-effort removal using the same CSV (if present): delete rows matching proposal_id+association_id.
    """
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if not insp.has_table(APPROVALS_TBL):
        log.info("[%s] downgrade: table %s not found; nothing to delete", revision, APPROVALS_TBL)
        return

    csv_path = _default_output_path(CSV_NAME)
    if not csv_path.exists():
        log.info("[%s] downgrade: CSV %s not found; skipping delete.", revision, csv_path)
        return

    reader, fobj = _open_csv(csv_path)
    deleted = 0
    try:
        with _outer_tx(bind):
            for idx, raw in enumerate(reader, start=1):
                pid = (raw.get("proposal_id") or "").strip()
                aid = (raw.get("association_id") or "").strip()
                if not pid or not aid:
                    if LOG_ROWS:
                        log.warning("[%s] downgrade row %d missing ids; skipping: %r", revision, idx, raw)
                    continue
                try:
                    res = bind.execute(
                        sa.text(
                            f"DELETE FROM {APPROVALS_TBL} "
                            f"WHERE proposal_id = :pid AND association_id = :aid"
                        ),
                        {"pid": pid, "aid": aid},
                    )
                    try:
                        rc = res.rowcount or 0
                        deleted += rc
                        if LOG_ROWS:
                            log.info("[%s] downgrade row %d DELETE ok; removed=%s", revision, idx, rc)
                    except Exception:
                        pass
                except Exception:
                    log.exception("[%s] downgrade delete failed for (%s,%s)", revision, pid, aid)
    finally:
        try:
            fobj.close()
        except Exception:
            pass

    log.info("[%s] downgrade removed ~%s rows from %s (based on CSV).",
             revision, deleted, APPROVALS_TBL)
