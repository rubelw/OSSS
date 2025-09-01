from __future__ import annotations

import os, csv, logging, random, json
from pathlib import Path
from contextlib import nullcontext
from typing import Optional

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

# ---- Alembic identifiers ----
revision = "0076_populate_accomodtns"
down_revision = "0076_populate_iep_plans"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

# ---- Config / env toggles ----------------------------------------------------
LOG_LVL        = os.getenv("ACC_LOG_LEVEL", "INFO").upper()
LOG_SQL        = os.getenv("ACC_LOG_SQL", "1") == "1"
LOG_ROWS       = os.getenv("ACC_LOG_ROWS", "1") == "1"
ABORT_IF_ZERO  = os.getenv("ACC_ABORT_IF_ZERO", "1") == "1"

CSV_ENV        = "ACCOMMODATIONS_CSV_PATH"  # override path if set
CSV_NAME       = "accomodations.csv"        # requested spelling

# how many rows per IEP plan to write; default 1 simple seed
ACC_PER_IEP    = int(os.getenv("ACC_PER_IEP", "1"))

# ---- Table names -------------------------------------------------------------
IEP_TBL        = "iep_plans"
ACC_TBL        = "accommodations"

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
    """Prefer gen_random_uuid(), then uuid_generate_v4(), else parameterized."""
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
    Always (re)write accomodations.csv with one (or ACC_PER_IEP) row per IEP plan.
    Returns (path, number_of_ieps).
    """
    out = _default_output_path(CSV_NAME)
    out.parent.mkdir(parents=True, exist_ok=True)

    insp = sa.inspect(bind)
    if not insp.has_table(IEP_TBL):
        log.warning("[%s] Table %s not found; writing header-only CSV.", revision, IEP_TBL)
        with out.open("w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(["iep_plan_id", "applies_to", "description"])
        return out, 0

    rows = bind.execute(sa.text(f"SELECT id FROM {IEP_TBL} ORDER BY id")).fetchall()
    iep_ids = [str(r[0]) for r in rows]

    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["iep_plan_id", "applies_to", "description"])
        for iep_id in iep_ids:
            for _ in range(ACC_PER_IEP):
                w.writerow([iep_id, "", "Seeded accommodation"])

    log.info("[%s] CSV generated with %d IEP plan(s) × %d rows => %s",
             revision, len(iep_ids), ACC_PER_IEP, out)
    return out, len(iep_ids)


def _open_csv(csv_path: Path):
    f = csv_path.open("r", encoding="utf-8", newline="")
    reader = csv.DictReader(f)
    log.info("[%s] CSV headers: %s", revision, reader.fieldnames)
    # preview a few rows
    try:
        from itertools import islice
        sample = list(islice(reader, 5))
        log.info("[%s] First rows preview: %s", revision, sample)
        f.seek(0); next(reader)  # rewind after header
    except Exception:
        pass
    return reader, f


def _insert_sql(bind):
    """
    Build an INSERT that avoids duplicates:
      - If a unique constraint exists including (iep_plan_id, description, applies_to),
        use ON CONFLICT DO NOTHING (Postgres).
      - Else fall back to INSERT … SELECT … WHERE NOT EXISTS … guard.
        For Postgres, use IS NOT DISTINCT FROM to be NULL-safe on applies_to.
    """
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns(ACC_TBL)}

    insert_cols: list[str] = []
    select_vals: list[str] = []

    # id
    uuid_expr = _uuid_sql(bind)
    insert_cols.append("id")
    select_vals.append(uuid_expr if uuid_expr != ":_uuid" else ":_uuid")

    def add(col: str, param: Optional[str] = None):
        if col in cols:
            insert_cols.append(col)
            select_vals.append(f":{param or col}")

    add("iep_plan_id")
    add("applies_to")
    add("description")
    # Let DB defaults fill created_at/updated_at

    col_list = ", ".join(insert_cols)
    select_list = ", ".join(select_vals)

    # Try to find a suitable unique constraint
    uqs = {u["name"]: u for u in insp.get_unique_constraints(ACC_TBL)}
    conflict_name = None
    for name, u in uqs.items():
        cset = set(u.get("column_names") or [])
        if {"iep_plan_id", "description", "applies_to"}.issubset(cset):
            conflict_name = name
            break

    if bind.dialect.name == "postgresql" and conflict_name:
        sql = sa.text(
            f"INSERT INTO {ACC_TBL} ({col_list}) "
            f"VALUES ({select_list}) "
            f"ON CONFLICT ON CONSTRAINT {conflict_name} DO NOTHING"
        )
    else:
        # Guard against duplicates
        if bind.dialect.name == "postgresql":
            # NULL-safe comparisons
            guard = (
                f" WHERE NOT EXISTS ("
                f"SELECT 1 FROM {ACC_TBL} "
                f"WHERE iep_plan_id = :iep_plan_id "
                f"AND description = :description "
                f"AND applies_to IS NOT DISTINCT FROM :applies_to)"
            )
        else:
            # Portable (not perfectly NULL-safe)
            guard = (
                f" WHERE NOT EXISTS ("
                f"SELECT 1 FROM {ACC_TBL} "
                f"WHERE iep_plan_id = :iep_plan_id "
                f"AND description = :description "
                f"AND ((applies_to = :applies_to) OR (applies_to IS NULL AND :applies_to IS NULL)))"
            )

        sql = sa.text(
            f"INSERT INTO {ACC_TBL} ({col_list}) "
            f"SELECT {select_list}{guard}"
        )

    needs_uuid_param = (uuid_expr == ":_uuid")
    return sql, cols, needs_uuid_param


# ---- Migration ---------------------------------------------------------------
def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if not insp.has_table(ACC_TBL):
        log.info("[%s] Table %s missing; nothing to populate.", revision, ACC_TBL)
        return

    csv_path, iep_count = _write_csv(bind)
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

                iep_plan_id = row.get("iep_plan_id") or None
                applies_to  = row.get("applies_to") or None
                description = row.get("description") or None

                if not iep_plan_id or not description:
                    skipped += 1
                    if LOG_ROWS:
                        log.warning("[%s] row %d missing iep_plan_id/description — skipping: %r",
                                    revision, idx, row)
                    continue

                params = {
                    "iep_plan_id": iep_plan_id,
                    "applies_to": applies_to,  # may be None/empty -> treat as None
                    "description": description,
                }
                if needs_uuid_param:
                    import uuid as _uuid
                    params["_uuid"] = str(_uuid.uuid4())

                # trim to known cols + _uuid
                params = {k: v for k, v in params.items() if (k in cols or k == "_uuid")}

                try:
                    bind.execute(insert_stmt, params)
                    inserted += 1
                    if LOG_ROWS:
                        log.info("[%s] row %d INSERT ok (iep_plan_id=%s)", revision, idx, iep_plan_id)
                except Exception:
                    skipped += 1
                    if LOG_ROWS:
                        log.exception("[%s] row %d INSERT failed; params=%r", revision, idx, params)
    finally:
        try:
            fobj.close()
        except Exception:
            pass

    log.info("[%s] CSV rows=%d, inserted=%d, skipped=%d (file=%s)", revision, total, inserted, skipped, csv_path)

    if ABORT_IF_ZERO and iep_count > 0 and inserted == 0:
        raise RuntimeError(f"[{revision}] No rows inserted; set ACC_LOG_ROWS=1 for per-row details.")


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if insp.has_table(ACC_TBL):
        try:
            res = bind.execute(sa.text(
                f"DELETE FROM {ACC_TBL} WHERE description = 'Seeded accommodation'"
            ))
            try:
                log.info("[%s] downgrade removed %s seeded rows from %s", revision, res.rowcount, ACC_TBL)
            except Exception:
                pass
        except Exception:
            log.exception("[%s] downgrade best-effort delete failed", revision)