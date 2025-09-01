"""Populate motions from CSV (auto-generate CSV each run, robust parsing, no manual transactions)."""

from __future__ import annotations

import os, csv, logging, random, json
from pathlib import Path
from contextlib import nullcontext
from typing import Optional

from sqlalchemy.dialects import postgresql as pg
from alembic import op
import sqlalchemy as sa

# ---- Alembic identifiers ----
revision = "0074_populate_curr_units"
down_revision = "0073_populate_curricula"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

# ---- Config / env toggles ----------------------------------------------------
LOG_LVL        = os.getenv("CU_LOG_LEVEL", "DEBUG").upper()
LOG_SQL        = os.getenv("CU_LOG_SQL", "1") == "1"
LOG_ROWS       = os.getenv("CU_LOG_ROWS", "1") == "1"
ABORT_IF_ZERO  = os.getenv("CU_ABORT_IF_ZERO", "1") == "1"
CSV_ENV        = "CURRICULUM_UNITS_CSV_PATH"
CSV_NAME       = "curriculum_units.csv"
CU_UNITS_PER_CURR = int(os.getenv("CU_UNITS_PER_CURR", "3"))
CU_SEED           = os.getenv("CU_SEED")

# ---- Table names -------------------------------------------------------------
CURRICULA_TBL = "curricula"
UNITS_TBL     = "curriculum_units"
PROPOSALS_TBL = "proposals"

# ---- Logging setup -----------------------------------------------------------
logging.getLogger("alembic.runtime.migration").setLevel(getattr(logging, LOG_LVL, logging.INFO))
engine_logger = logging.getLogger("sqlalchemy.engine")
engine_logger.setLevel(logging.INFO if LOG_SQL else getattr(logging, LOG_LVL, logging.INFO))

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

def _ensure_schema(bind):
    insp = sa.inspect(bind)

    # proposals.curriculum_id (nullable) + index + FK → curricula(id)
    if insp.has_table(PROPOSALS_TBL):
        props_cols = {c["name"] for c in insp.get_columns(PROPOSALS_TBL)}
        if "curriculum_id" not in props_cols:
            coltype = pg.UUID(as_uuid=False) if bind.dialect.name == "postgresql" else sa.String(36)
            op.add_column(PROPOSALS_TBL, sa.Column("curriculum_id", coltype, nullable=True))
            try:
                op.create_index("ix_proposals_curriculum_id", PROPOSALS_TBL, ["curriculum_id"], unique=False)
            except Exception:
                pass
        fks = {fk["name"] for fk in insp.get_foreign_keys(PROPOSALS_TBL)}
        if "fk_proposals_curricula" not in fks:
            try:
                op.create_foreign_key(
                    "fk_proposals_curricula",
                    source_table=PROPOSALS_TBL,
                    referent_table=CURRICULA_TBL,
                    local_cols=["curriculum_id"],
                    remote_cols=["id"],
                    ondelete="SET NULL",
                )
            except Exception:
                pass

    # unique(uq_unit_order) on (curriculum_id, order_index) for ON CONFLICT
    if insp.has_table(UNITS_TBL):
        uqs = {u["name"]: u for u in insp.get_unique_constraints(UNITS_TBL)}
        desired_cols = ["curriculum_id", "order_index"]
        if "uq_unit_order" in uqs and uqs["uq_unit_order"]["column_names"] != desired_cols:
            op.drop_constraint("uq_unit_order", UNITS_TBL, type_="unique")
        if "uq_unit_order" not in uqs or (
            "uq_unit_order" in uqs and uqs["uq_unit_order"]["column_names"] != desired_cols
        ):
            try:
                op.create_unique_constraint("uq_unit_order", UNITS_TBL, desired_cols)
            except Exception:
                pass

def _write_csv(bind) -> tuple[Path, int]:
    """
    Always (re)write curriculum_units.csv.
    Returns (path, number_of_curricula).
    If there are no curricula, write a header-only CSV and return (path, 0).
    """
    out = _default_output_path(CSV_NAME)
    out.parent.mkdir(parents=True, exist_ok=True)

    insp = sa.inspect(bind)
    if not insp.has_table(CURRICULA_TBL):
        log.warning("[%s] Table %s not found; writing header-only CSV.", revision, CURRICULA_TBL)
        with out.open("w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(["curriculum_id", "title", "order_index", "summary", "metadata"])
        return out, 0

    rows = bind.execute(sa.text(f"SELECT id FROM {CURRICULA_TBL} ORDER BY id")).fetchall()
    cur_ids = [str(r[0]) for r in rows]

    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["curriculum_id", "title", "order_index", "summary", "metadata"])
        if not cur_ids:
            log.warning("[%s] No curriculum present; header-only CSV written: %s", revision, out)
            return out, 0

        rng = random.Random(CU_SEED)
        for cid in cur_ids:
            for idx in range(1, CU_UNITS_PER_CURR + 1):
                title = f"Unit {idx} for {cid[:8]}"
                summary = "Seeded Curriculum Unit"
                metadata = {"seed": True, "idx": idx}
                w.writerow([cid, title, idx, summary, json.dumps(metadata)])

    log.info("[%s] CSV generated with %d curriculum × %d units => %s",
             revision, len(cur_ids), CU_UNITS_PER_CURR, out)
    return out, len(cur_ids)

def _open_csv(csv_path: Path):
    f = csv_path.open("r", encoding="utf-8", newline="")
    reader = csv.DictReader(f)
    log.info("[%s] CSV headers: %s", revision, reader.fieldnames)
    # peek first 5 rows for debugging
    try:
        from itertools import islice
        rows = list(islice(reader, 5))
        log.info("[%s] First rows preview: %s", revision, rows)
        f.seek(0); next(reader)  # rewind after header
    except Exception:
        pass
    return reader, f

def _insert_sql(bind):
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns(UNITS_TBL)}

    ins_cols = []
    vals     = []

    # choose UUID generation
    uuid_expr = _uuid_sql(bind)
    if uuid_expr == ":_uuid":
        ins_cols.append("id"); vals.append(":_uuid")
    else:
        ins_cols.append("id"); vals.append(uuid_expr)

    def add(col: str, param: Optional[str] = None):
        if col in cols:
            ins_cols.append(col)
            vals.append(f":{param or col}")

    add("curriculum_id")
    add("title")
    add("order_index")
    add("summary")
    add("metadata", "metadata_json")

    if "created_at" in cols:
        ins_cols.append("created_at"); vals.append("now()")
    if "updated_at" in cols:
        ins_cols.append("updated_at"); vals.append("now()")

    base_sql = f"INSERT INTO {UNITS_TBL} ({', '.join(ins_cols)}) VALUES ({', '.join(vals)})"

    # Try ON CONFLICT if the named constraint exists; otherwise fall back to NOT EXISTS guard.
    uqs = {u["name"]: u for u in insp.get_unique_constraints(UNITS_TBL)}
    if bind.dialect.name == "postgresql" and "uq_unit_order" in uqs:
        sql = sa.text(base_sql + " ON CONFLICT ON CONSTRAINT uq_unit_order DO NOTHING")
        use_guard = False
    else:
        guard = (
            f" WHERE NOT EXISTS (SELECT 1 FROM {UNITS_TBL} "
            f"WHERE curriculum_id = :curriculum_id AND order_index = :order_index)"
        )
        sql = sa.text(base_sql + guard)
        use_guard = True

    # --- NEW: bind JSON param so psycopg2 knows to serialize dicts properly ---
    sql = sql.bindparams(sa.bindparam("metadata_json", type_=sa.JSON))

    return sql, cols, (uuid_expr == ":_uuid")

# ---- Migration ---------------------------------------------------------------
def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    _ensure_schema(bind)

    if not insp.has_table(UNITS_TBL):
        log.info("[%s] Table %s missing; nothing to populate.", revision, UNITS_TBL)
        return

    csv_path, curricula_count = _write_csv(bind)
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

                curriculum_id = row.get("curriculum_id") or None
                title         = row.get("title") or None
                if not curriculum_id or not title:
                    skipped += 1
                    if LOG_ROWS:
                        log.warning("[%s] row %d missing curriculum_id/title — skipping: %r", revision, idx, row)
                    continue

                try:
                    order_index = int(row.get("order_index") or 0)
                except Exception:
                    order_index = 0

                metadata_json = None
                mv = row.get("metadata")
                if mv:
                    try:
                        metadata_json = json.loads(mv)
                    except Exception:
                        metadata_json = {"raw": mv}

                params = {
                    "curriculum_id": curriculum_id,
                    "title": title,
                    "order_index": order_index,
                    "summary": (row.get("summary") or None),
                    "metadata_json": metadata_json,
                }
                if needs_uuid_param:
                    import uuid as _uuid
                    params["_uuid"] = str(_uuid.uuid4())

                params = {k: v for k, v in params.items()
                          if (k in cols) or (k == "metadata_json" and "metadata" in cols) or (k == "_uuid")}

                try:
                    bind.execute(insert_stmt, params)
                    inserted += 1
                    if LOG_ROWS:
                        log.info("[%s] row %d INSERT ok (curriculum_id=%s, order_index=%s, title=%r)",
                                 revision, idx, curriculum_id, order_index, title)
                except Exception as ex:
                    skipped += 1
                    msg = str(ex)
                    reason = "unknown"
                    if "foreign key" in msg.lower():
                        reason = "fk_violation"
                    elif "uuid" in msg.lower() and "function" in msg.lower():
                        reason = "uuid_function_missing"
                    elif "unique" in msg.lower() or "duplicate" in msg.lower():
                        reason = "duplicate"
                    if LOG_ROWS:
                        log.exception("[%s] row %d INSERT failed (%s); params=%r", revision, idx, reason, params)

    finally:
        try:
            fobj.close()
        except Exception:
            pass

    log.info("[%s] CSV rows=%d, inserted=%d, skipped=%d (file=%s)", revision, total, inserted, skipped, csv_path)

    if ABORT_IF_ZERO and curricula_count > 0 and inserted == 0:
        raise RuntimeError(f"[{revision}] No rows inserted; set CU_LOG_ROWS=1 for per-row details.")

def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if insp.has_table(UNITS_TBL):
        try:
            res = bind.execute(sa.text(
                f"DELETE FROM {UNITS_TBL} WHERE summary = 'Seeded Curriculum Unit'"
            ))
            try:
                log.info("[%s] downgrade removed %s seeded rows from %s", revision, res.rowcount, UNITS_TBL)
            except Exception:
                pass
        except Exception:
            log.exception("[%s] downgrade best-effort delete failed", revision)

    if insp.has_table(PROPOSALS_TBL):
        try:
            op.drop_constraint("fk_proposals_curricula", PROPOSALS_TBL, type_="foreignkey")
        except Exception:
            pass
        try:
            op.drop_index("ix_proposals_curriculum_id", table_name=PROPOSALS_TBL)
        except Exception:
            pass
        try:
            cols = {c["name"] for c in insp.get_columns(PROPOSALS_TBL)}
            if "curriculum_id" in cols:
                op.drop_column(PROPOSALS_TBL, "curriculum_id")
        except Exception:
            pass
