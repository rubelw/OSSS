from __future__ import annotations

import os, csv, logging, random, json, uuid
from pathlib import Path
from contextlib import nullcontext
from typing import Optional

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

# ---- Alembic identifiers ----
revision = "0080_populate_agenda_itm_app"
down_revision = "0079_populate_agenda_wf_stp"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")


# ---- Config / env toggles ----------------------------------------------------
LOG_LVL        = os.getenv("AIA_LOG_LEVEL", "INFO").upper()
LOG_SQL        = os.getenv("AIA_LOG_SQL", "1") == "1"
LOG_ROWS       = os.getenv("AIA_LOG_ROWS", "1") == "1"
ABORT_IF_ZERO  = os.getenv("AIA_ABORT_IF_ZERO", "1") == "1"

CSV_ENV        = "AGENDA_ITEM_APPROVALS_CSV_PATH"   # file or directory override
CSV_NAME       = "agenda_item_approvals.csv"

# how many approvals per item to seed (e.g., 1 = link each item to one step)
AIA_STEPS_PER_ITEM = int(os.getenv("AIA_STEPS_PER_ITEM", "1"))
AIA_SEED           = os.getenv("AIA_SEED")  # optional deterministic seeding

# ---- Table names -------------------------------------------------------------
ITEMS_TBL    = "agenda_items"
STEPS_TBL    = "agenda_workflow_steps"
TARGET_TBL   = "agenda_item_approvals"

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
    """Ensure a unique constraint on (item_id, step_id) for conflict handling."""
    insp = sa.inspect(bind)
    if not insp.has_table(TARGET_TBL):
        return
    uqs = {u["name"]: u for u in insp.get_unique_constraints(TARGET_TBL)}
    desired_cols = ["item_id", "step_id"]
    if "uq_aia_item_step" in uqs and uqs["uq_aia_item_step"]["column_names"] != desired_cols:
        op.drop_constraint("uq_aia_item_step", TARGET_TBL, type_="unique")
    if "uq_aia_item_step" not in uqs or (
        "uq_aia_item_step" in uqs and uqs["uq_aia_item_step"]["column_names"] != desired_cols
    ):
        try:
            op.create_unique_constraint("uq_aia_item_step", TARGET_TBL, desired_cols)
        except Exception:
            # best effort; may already exist
            pass


def _write_csv(bind) -> tuple[Path, int, int]:
    """
    Always (re)write agenda_item_approvals.csv.
    Returns (path, num_items, num_steps).
    """
    out = _default_output_path(CSV_NAME)
    out.parent.mkdir(parents=True, exist_ok=True)

    insp = sa.inspect(bind)
    has_items = insp.has_table(ITEMS_TBL)
    has_steps = insp.has_table(STEPS_TBL)

    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["item_id", "step_id", "approver_id", "decision", "decided_at", "comment"])

        if not (has_items and has_steps):
            log.warning("[%s] Missing %s or %s; header-only CSV written: %s",
                        revision, ITEMS_TBL, STEPS_TBL, out)
            return out, 0, 0

        item_rows = bind.execute(sa.text(f"SELECT id FROM {ITEMS_TBL} ORDER BY id")).fetchall()
        step_rows = bind.execute(sa.text(f"SELECT id FROM {STEPS_TBL} ORDER BY workflow_id, step_no, id")).fetchall()
        item_ids = [str(r[0]) for r in item_rows]
        step_ids = [str(r[0]) for r in step_rows]

        if not item_ids or not step_ids:
            log.warning("[%s] No items or no steps; header-only CSV written: %s", revision, out)
            return out, len(item_ids), len(step_ids)

        rng = random.Random(AIA_SEED)
        # round-robin through steps by default
        for i_idx, item_id in enumerate(item_ids):
            # choose a starting offset so items distribute across steps
            base = i_idx % len(step_ids)
            for k in range(max(1, AIA_STEPS_PER_ITEM)):
                step_id = step_ids[(base + k) % len(step_ids)]
                # approver/decision fields optional; leave empty (=> NULL)
                w.writerow([item_id, step_id, "", "", "", "Seeded AgendaItemApproval"])

    log.info("[%s] CSV generated: items=%d, steps=%d, file=%s", revision, len(item_ids), len(step_ids), out)
    return out, len(item_ids), len(step_ids)


def _open_csv(csv_path: Path):
    f = csv_path.open("r", encoding="utf-8", newline="")
    reader = csv.DictReader(f)
    log.info("[%s] CSV headers: %s", revision, reader.fieldnames)
    # preview a few rows
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
    Build INSERT that avoids duplicates based on (item_id, step_id).
    If a unique constraint exists, use ON CONFLICT; else portable NOT EXISTS guard.
    """
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns(TARGET_TBL)}

    insert_cols: list[str] = []
    select_vals: list[str] = []

    uuid_expr = _uuid_sql(bind)
    insert_cols.append("id")
    select_vals.append(uuid_expr if uuid_expr != ":_uuid" else ":_uuid")

    def add(col: str, param: Optional[str] = None):
        if col in cols:
            insert_cols.append(col)
            select_vals.append(f":{param or col}")

    add("item_id")
    add("step_id")
    add("approver_id")
    add("decision")
    add("decided_at")
    add("comment")

    # if created_at/updated_at exist, set now()
    if "created_at" in cols:
        insert_cols.append("created_at"); select_vals.append("now()")
    if "updated_at" in cols:
        insert_cols.append("updated_at"); select_vals.append("now()")

    col_list   = ", ".join(insert_cols)
    values_sql = ", ".join(select_vals)

    # find suitable unique constraint
    uqs = {u["name"]: u for u in insp.get_unique_constraints(TARGET_TBL)}
    conflict_name = None
    for name, u in uqs.items():
        cset = set(u.get("column_names") or [])
        if {"item_id", "step_id"}.issubset(cset):
            conflict_name = name
            break

    if bind.dialect.name == "postgresql" and conflict_name:
        stmt = sa.text(
            f"INSERT INTO {TARGET_TBL} ({col_list}) "
            f"VALUES ({values_sql}) "
            f"ON CONFLICT ON CONSTRAINT {conflict_name} DO NOTHING"
        )
    else:
        # Portable pattern: INSERT ... SELECT ... WHERE NOT EXISTS (...)
        stmt = sa.text(
            f"INSERT INTO {TARGET_TBL} ({col_list}) "
            f"SELECT {values_sql} "
            f"WHERE NOT EXISTS ("
            f"  SELECT 1 FROM {TARGET_TBL} "
            f"  WHERE item_id = :item_id AND step_id = :step_id"
            f")"
        )

    needs_uuid_param = (uuid_expr == ":_uuid")
    return stmt, cols, needs_uuid_param


# ---- Migration ---------------------------------------------------------------
def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    _ensure_schema(bind)

    if not insp.has_table(TARGET_TBL):
        log.info("[%s] Table %s missing; nothing to populate.", revision, TARGET_TBL)
        return

    csv_path, n_items, n_steps = _write_csv(bind)
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

                item_id     = row.get("item_id") or None
                step_id     = row.get("step_id") or None
                approver_id = row.get("approver_id") or None
                decision    = row.get("decision") or None
                decided_at  = row.get("decided_at") or None  # expect '', ISO8601, or DB-castable
                comment     = row.get("comment") or None

                if not item_id or not step_id:
                    skipped += 1
                    if LOG_ROWS:
                        log.warning("[%s] row %d missing item_id/step_id — skipping: %r", revision, idx, row)
                    continue

                # normalize empties -> NULL
                approver_id = None if not approver_id else approver_id
                decision    = None if not decision else decision
                decided_at  = None if not decided_at else decided_at
                comment     = None if not comment else comment

                params = {
                    "item_id": item_id,
                    "step_id": step_id,
                    "approver_id": approver_id,
                    "decision": decision,
                    "decided_at": decided_at,
                    "comment": comment,
                }
                if needs_uuid_param:
                    params["_uuid"] = str(uuid.uuid4())

                # keep only known params (+ _uuid)
                params = {k: v for k, v in params.items() if (k in cols or k == "_uuid")}

                try:
                    bind.execute(insert_stmt, params)
                    inserted += 1
                    if LOG_ROWS:
                        log.info("[%s] row %d INSERT ok (item_id=%s, step_id=%s)",
                                 revision, idx, item_id, step_id)
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

    if ABORT_IF_ZERO and n_items > 0 and n_steps > 0 and inserted == 0:
        raise RuntimeError(f"[{revision}] No rows inserted; set AIA_LOG_ROWS=1 for per-row details.")


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if insp.has_table(TARGET_TBL):
        try:
            # Best-effort delete: remove rows we likely seeded (by comment marker)
            res = bind.execute(sa.text(
                f"DELETE FROM {TARGET_TBL} WHERE comment = 'Seeded AgendaItemApproval'"
            ))
            try:
                log.info("[%s] downgrade removed %s seeded rows from %s",
                         revision, res.rowcount, TARGET_TBL)
            except Exception:
                pass
        except Exception:
            log.exception("[%s] downgrade best-effort delete failed", revision)