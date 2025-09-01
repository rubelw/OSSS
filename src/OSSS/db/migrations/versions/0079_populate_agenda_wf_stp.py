from __future__ import annotations

import os, csv, logging, random, json, uuid
from pathlib import Path
from contextlib import nullcontext
from typing import Optional

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

# ---- Alembic identifiers ----
revision = "0079_populate_agenda_wf_stp"
down_revision = "0078_populate_activities"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")


# ---- Config / env toggles ----------------------------------------------------
LOG_LVL        = os.getenv("AWF_LOG_LEVEL", "INFO").upper()
LOG_SQL        = os.getenv("AWF_LOG_SQL", "1") == "1"
LOG_ROWS       = os.getenv("AWF_LOG_ROWS", "1") == "1"
ABORT_IF_ZERO  = os.getenv("AWF_ABORT_IF_ZERO", "1") == "1"

CSV_ENV        = "AWF_STEPS_CSV_PATH"  # file or directory override
CSV_NAME       = "agenda_workflow_steps.csv"

STEPS_PER_WF   = int(os.getenv("AWF_STEPS_PER_WF", "2"))  # default 2 steps per workflow
AWF_SEED       = os.getenv("AWF_SEED")  # optional deterministic seeding

# ---- Table names -------------------------------------------------------------
WF_TBL         = "agenda_workflows"
STEPS_TBL      = "agenda_workflow_steps"

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
    """Prefer gen_random_uuid(), then uuid_generate_v4(), else parameterize."""
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


def _ensure_schema(bind):
    """Ensure a unique constraint on (workflow_id, step_no) for conflict handling."""
    insp = sa.inspect(bind)
    if not insp.has_table(STEPS_TBL):
        return
    uqs = {u["name"]: u for u in insp.get_unique_constraints(STEPS_TBL)}
    desired_cols = ["workflow_id", "step_no"]
    # Create/repair unique constraint if needed
    if "uq_awf_workflow_stepno" in uqs and uqs["uq_awf_workflow_stepno"]["column_names"] != desired_cols:
        op.drop_constraint("uq_awf_workflow_stepno", STEPS_TBL, type_="unique")
    if "uq_awf_workflow_stepno" not in uqs or (
        "uq_awf_workflow_stepno" in uqs and uqs["uq_awf_workflow_stepno"]["column_names"] != desired_cols
    ):
        try:
            op.create_unique_constraint("uq_awf_workflow_stepno", STEPS_TBL, desired_cols)
        except Exception:
            pass


def _write_csv(bind) -> tuple[Path, int]:
    """
    Always (re)write agenda_workflow_steps.csv with STEPS_PER_WF rows per workflow.
    Columns: workflow_id, step_no, approver_type, approver_id, rule
    """
    out = _default_output_path(CSV_NAME)
    out.parent.mkdir(parents=True, exist_ok=True)

    insp = sa.inspect(bind)
    if not insp.has_table(WF_TBL):
        log.warning("[%s] Table %s not found; writing header-only CSV.", revision, WF_TBL)
        with out.open("w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(["workflow_id", "step_no", "approver_type", "approver_id", "rule"])
        return out, 0

    rows = bind.execute(sa.text(f"SELECT id FROM {WF_TBL} ORDER BY id")).fetchall()
    wf_ids = [str(r[0]) for r in rows]

    rng = random.Random(AWF_SEED)
    approver_types = ["principal", "assistant_principal", "superintendent", "board", "role"]
    rules = ["auto-approve", "majority", "unanimous", "manual", "threshold"]

    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["workflow_id", "step_no", "approver_type", "approver_id", "rule"])
        for wid in wf_ids:
            for n in range(1, max(STEPS_PER_WF, 1) + 1):
                apptype = rng.choice(approver_types)
                rule = rng.choice(rules)
                # approver_id optional; leave empty most of the time
                approver_id = "" if rng.random() < 0.8 else str(uuid.uuid4())
                w.writerow([wid, n, apptype, approver_id, rule])

    log.info("[%s] CSV generated with %d workflow(s) × %d steps => %s",
             revision, len(wf_ids), max(STEPS_PER_WF, 1), out)
    return out, len(wf_ids)


def _open_csv(csv_path: Path):
    f = csv_path.open("r", encoding="utf-8", newline="")
    reader = csv.DictReader(f)
    log.info("[%s] CSV headers: %s", revision, reader.fieldnames)
    # quick preview
    try:
        from itertools import islice
        sample = list(islice(reader, 5))
        log.info("[%s] First rows preview: %s", revision, sample)
        f.seek(0); next(reader)
    except Exception:
        pass
    return reader, f


def _insert_sql(bind):
    """
    Build INSERT that avoids duplicates based on (workflow_id, step_no).
    If a unique constraint exists (uq_awf_workflow_stepno), use ON CONFLICT; else NOT EXISTS guard.
    """
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns(STEPS_TBL)}

    insert_cols: list[str] = []
    select_vals: list[str] = []

    uuid_expr = _uuid_sql(bind)
    insert_cols.append("id")
    select_vals.append(uuid_expr if uuid_expr != ":_uuid" else ":_uuid")

    def add(col: str, param: Optional[str] = None):
        if col in cols:
            insert_cols.append(col)
            select_vals.append(f":{param or col}")

    add("workflow_id")
    add("step_no")
    add("approver_type")
    add("approver_id")
    add("rule")

    # created_at/updated_at if they exist (not in model, but harmless if present)
    if "created_at" in cols:
        insert_cols.append("created_at"); select_vals.append("now()")
    if "updated_at" in cols:
        insert_cols.append("updated_at"); select_vals.append("now()")

    col_list = ", ".join(insert_cols)
    select_list = ", ".join(select_vals)

    # Find suitable unique constraint
    uqs = {u["name"]: u for u in insp.get_unique_constraints(STEPS_TBL)}
    conflict_name = None
    for name, u in uqs.items():
        cset = set(u.get("column_names") or [])
        if {"workflow_id", "step_no"}.issubset(cset):
            conflict_name = name
            break

    if bind.dialect.name == "postgresql" and conflict_name:
        sql = sa.text(
            f"INSERT INTO {STEPS_TBL} ({col_list}) "
            f"VALUES ({select_list}) "
            f"ON CONFLICT ON CONSTRAINT {conflict_name} DO NOTHING"
        )
    else:
        # Portable NOT EXISTS guard
        sql = sa.text(
            f"INSERT INTO {STEPS_TBL} ({col_list}) "
            f"SELECT {select_list} "
            f"WHERE NOT EXISTS ("
            f"  SELECT 1 FROM {STEPS_TBL} "
            f"  WHERE workflow_id = :workflow_id AND step_no = :step_no"
            f")"
        )

    needs_uuid_param = (uuid_expr == ":_uuid")
    return sql, cols, needs_uuid_param


# ---- Migration ---------------------------------------------------------------
def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    _ensure_schema(bind)

    if not insp.has_table(STEPS_TBL):
        log.info("[%s] Table %s missing; nothing to populate.", revision, STEPS_TBL)
        return

    csv_path, wf_count = _write_csv(bind)
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

                workflow_id   = row.get("workflow_id") or None
                step_no_raw   = row.get("step_no") or None
                approver_type = row.get("approver_type") or None
                approver_id   = row.get("approver_id") or None
                rule          = row.get("rule") or None

                # Basic validations / coercions
                try:
                    step_no = int(step_no_raw) if step_no_raw is not None else None
                except Exception:
                    step_no = None

                approver_id = None if not approver_id else approver_id  # empty => NULL

                if not workflow_id or step_no is None or not approver_type:
                    skipped += 1
                    if LOG_ROWS:
                        log.warning(
                            "[%s] row %d missing workflow_id/step_no/approver_type — skipping: %r",
                            revision, idx, row
                        )
                    continue

                params = {
                    "workflow_id": workflow_id,
                    "step_no": step_no,
                    "approver_type": approver_type,
                    "approver_id": approver_id,
                    "rule": rule,
                }
                if needs_uuid_param:
                    params["_uuid"] = str(uuid.uuid4())

                # Keep only params that match real columns (+ _uuid)
                params = {k: v for k, v in params.items() if (k in cols or k == "_uuid")}

                try:
                    bind.execute(insert_stmt, params)
                    inserted += 1
                    if LOG_ROWS:
                        log.info("[%s] row %d INSERT ok (workflow_id=%s, step_no=%s)",
                                 revision, idx, workflow_id, step_no)
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

    if ABORT_IF_ZERO and wf_count > 0 and inserted == 0:
        raise RuntimeError(f"[{revision}] No rows inserted; set AWF_LOG_ROWS=1 for per-row details.")


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if insp.has_table(STEPS_TBL):
        try:
            # Best-effort delete: remove rows whose rule matches our seeded set
            res = bind.execute(sa.text(
                f"DELETE FROM {STEPS_TBL} "
                f"WHERE rule IN ('auto-approve','majority','unanimous','manual','threshold')"
            ))
            try:
                log.info("[%s] downgrade removed %s seeded rows from %s",
                         revision, res.rowcount, STEPS_TBL)
            except Exception:
                pass
        except Exception:
            log.exception("[%s] downgrade best-effort delete failed", revision)