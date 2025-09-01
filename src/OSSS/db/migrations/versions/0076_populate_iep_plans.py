from __future__ import annotations

import os, csv, logging, random, json
from pathlib import Path
from contextlib import nullcontext
from typing import Optional

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

# ---- Alembic identifiers ----
revision = "0076_populate_iep_plans"
down_revision = "0075_populate_curriculum_ver"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")


# ---- Config / env toggles ----------------------------------------------------
LOG_LVL        = os.getenv("IEP_LOG_LEVEL", "DEBUG").upper()
LOG_SQL        = os.getenv("IEP_LOG_SQL", "1") == "1"
LOG_ROWS       = os.getenv("IEP_LOG_ROWS", "1") == "1"  # per-row logging off by default
ABORT_IF_ZERO  = os.getenv("IEP_ABORT_IF_ZERO", "1") == "1"

CSV_ENV        = "IEP_PLANS_CSV_PATH"
CSV_NAME       = "iep_plans.csv"

IEP_PLANS_PER_CASE = int(os.getenv("IEP_PLANS_PER_CASE", "1"))
IEP_SEED            = os.getenv("IEP_SEED")  # deterministic if provided

# ---- Table names -------------------------------------------------------------
CASES_TBL  = "special_education_cases"
IEP_TBL    = "iep_plans"

# ---- Logging setup -----------------------------------------------------------
logging.getLogger("alembic.runtime.migration").setLevel(getattr(logging, LOG_LVL, logging.INFO))
engine_logger = logging.getLogger("sqlalchemy.engine")
engine_logger.setLevel(logging.INFO if LOG_SQL else getattr(logging, LOG_LVL, logging.INFO))

# ---- Helpers ----------------------------------------------------------------
def _outer_tx(conn):
    """Return a context that starts a tx only if we aren't already in one."""
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
    """Prefer gen_random_uuid(), fall back to uuid_generate_v4(), else parameterize."""
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
    Always (re)write iep_plans.csv with a header and rows derived from special_education_cases.
    Columns: special_ed_case_id, effective_start, effective_end, summary
    """
    out = _default_output_path(CSV_NAME)
    out.parent.mkdir(parents=True, exist_ok=True)

    insp = sa.inspect(bind)
    if not insp.has_table(CASES_TBL):
        log.warning("[%s] Table %s not found; writing header-only CSV.", revision, CASES_TBL)
        with out.open("w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(["special_ed_case_id", "effective_start", "effective_end", "summary"])
        return out, 0

    rows = bind.execute(sa.text(f"SELECT id FROM {CASES_TBL} ORDER BY id")).fetchall()
    case_ids = [str(r[0]) for r in rows]

    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["special_ed_case_id", "effective_start", "effective_end", "summary"])

        if not case_ids:
            log.info("[%s] No special_education_cases found; CSV contains only header: %s", revision, out)
            return out, 0

        rng = random.Random(IEP_SEED)
        # Simple deterministic date seeds: start = 2024-08-01 + offset; sometimes add an end date
        base_year, base_month, base_day = 2024, 8, 1
        for cid in case_ids:
            for n in range(IEP_PLANS_PER_CASE):
                # Effective start (spread by n to avoid identical pairs)
                y = base_year + (n // 12)
                m = base_month + (n % 12)
                while m > 12:
                    y += 1
                    m -= 12
                start = f"{y:04d}-{m:02d}-{base_day:02d}"

                # 50% chance to include an end date ~ 6 months after start
                if rng.random() < 0.5:
                    ey, em = y, m + 6
                    while em > 12:
                        ey += 1
                        em -= 12
                    end = f"{ey:04d}-{em:02d}-{base_day:02d}"
                else:
                    end = ""  # empty -> NULL

                summary = "Seeded IEP Plan"
                w.writerow([cid, start, end, summary])

    log.info("[%s] CSV generated with %d cases × %d plans => %s",
             revision, len(case_ids), IEP_PLANS_PER_CASE, out)
    return out, len(case_ids)


def _open_csv(csv_path: Path):
    f = csv_path.open("r", encoding="utf-8", newline="")
    reader = csv.DictReader(f)
    log.info("[%s] CSV headers: %s", revision, reader.fieldnames)
    return reader, f

def _insert_sql(bind):
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns(IEP_TBL)}

    insert_cols: list[str] = []
    values_for_select: list[str] = []  # SQL fragments used in SELECT (not VALUES)

    uuid_expr = _uuid_sql(bind)
    insert_cols.append("id")
    values_for_select.append(uuid_expr if uuid_expr != ":_uuid" else ":_uuid")

    def add(col: str, param: Optional[str] = None):
        if col in cols:
            insert_cols.append(col)
            values_for_select.append(f":{param or col}")

    add("special_ed_case_id")
    add("effective_start")
    add("effective_end")
    add("summary")
    # Let DB defaults fill created_at/updated_at

    col_list = ", ".join(insert_cols)

    # Prefer ON CONFLICT if we have a unique constraint that includes (special_ed_case_id, effective_start)
    uqs = {u["name"]: u for u in insp.get_unique_constraints(IEP_TBL)}
    conflict_name = None
    for name, u in uqs.items():
        cols_set = set(u.get("column_names") or [])
        if {"special_ed_case_id", "effective_start"}.issubset(cols_set):
            conflict_name = name
            break

    if bind.dialect.name == "postgresql" and conflict_name:
        sql = sa.text(
            f"INSERT INTO {IEP_TBL} ({col_list}) "
            f"VALUES ({', '.join(values_for_select)}) "
            f"ON CONFLICT ON CONSTRAINT {conflict_name} DO NOTHING"
        )
    else:
        # INSERT … SELECT … WHERE NOT EXISTS …
        select_list = ", ".join(values_for_select)
        guard = (
            f" WHERE NOT EXISTS ("
            f"SELECT 1 FROM {IEP_TBL} "
            f"WHERE special_ed_case_id = :special_ed_case_id "
            f"AND effective_start = :effective_start)"
        )
        sql = sa.text(
            f"INSERT INTO {IEP_TBL} ({col_list}) "
            f"SELECT {select_list}{guard}"
        )

    needs_uuid_param = (uuid_expr == ":_uuid")
    return sql, cols, needs_uuid_param


# ---- Migration ---------------------------------------------------------------
def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if not insp.has_table(IEP_TBL):
        log.info("[%s] Table %s missing; nothing to populate.", revision, IEP_TBL)
        return

    csv_path, cases_count = _write_csv(bind)
    reader, fobj = _open_csv(csv_path)
    insert_stmt, cols, needs_uuid_param = _insert_sql(bind)

    total = inserted = skipped = 0
    try:
        with _outer_tx(bind):
            for idx, raw in enumerate(reader, start=1):
                total += 1
                if not raw:
                    continue
                # Trim whitespace
                row = { (k.strip() if isinstance(k, str) else k): (v.strip() if isinstance(v, str) else v)
                        for k, v in raw.items() }

                case_id       = row.get("special_ed_case_id") or None
                eff_start     = row.get("effective_start") or None
                eff_end       = row.get("effective_end") or None
                summary       = row.get("summary") or None

                if not case_id or not eff_start:
                    skipped += 1
                    if LOG_ROWS:
                        log.warning("[%s] row %d missing case_id/effective_start — skipping: %r", revision, idx, row)
                    continue

                # Normalize empty → NULL
                eff_end = None if (eff_end in ("", "null", "NULL")) else eff_end

                params = {
                    "special_ed_case_id": case_id,
                    "effective_start": eff_start,
                    "effective_end": eff_end,
                    "summary": summary,
                }
                if needs_uuid_param:
                    import uuid as _uuid
                    params["_uuid"] = str(_uuid.uuid4())

                # Keep only real columns (and _uuid)
                params = {k: v for k, v in params.items() if (k in cols or k == "_uuid")}

                try:
                    bind.execute(insert_stmt, params)
                    inserted += 1
                    if LOG_ROWS:
                        log.info("[%s] row %d INSERT ok (case=%s, start=%s)", revision, idx, case_id, eff_start)
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

    if ABORT_IF_ZERO and cases_count > 0 and inserted == 0:
        raise RuntimeError(f"[{revision}] No rows inserted; set IEP_LOG_ROWS=1 for per-row details.")


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if insp.has_table(IEP_TBL):
        try:
            # Best-effort removal of just the seeded rows
            res = bind.execute(sa.text(
                f"DELETE FROM {IEP_TBL} WHERE summary = 'Seeded IEP Plan'"
            ))
            try:
                log.info("[%s] downgrade removed %s seeded rows from %s", revision, res.rowcount, IEP_TBL)
            except Exception:
                pass
        except Exception:
            log.exception("[%s] downgrade best-effort delete failed", revision)