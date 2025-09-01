# src/OSSS/db/migrations/versions/0081_populate_audit_logs.py
from __future__ import annotations

import os, csv, json, logging, uuid, random
from pathlib import Path
from contextlib import nullcontext
from typing import Optional
from sqlalchemy.dialects import postgresql as pg
from contextlib import nullcontext

from alembic import op
import sqlalchemy as sa

# ---- Alembic identifiers ----
revision = "0084_populate_alignments"
down_revision = "0083_populate_requirements"  # update if needed
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

# ---- Config / env toggles ----------------------------------------------------
LOG_LVL        = os.getenv("ALN_LOG_LEVEL", "DEBUG").upper()
LOG_SQL        = os.getenv("ALN_LOG_SQL", "1") == "1"
LOG_ROWS       = os.getenv("ALN_LOG_ROWS", "1") == "1"
ABORT_IF_ZERO  = os.getenv("ALN_ABORT_IF_ZERO", "1") == "1"

CSV_ENV        = "ALIGNMENTS_CSV_PATH"
CSV_NAME       = "alignments.csv"

ALN_PER_VERSION = int(os.getenv("ALN_PER_VERSION", "1"))          # how many requirements per curriculum_version
ALN_LEVELS      = os.getenv("ALN_LEVELS", "aligned,partial,not_aligned,unknown").split(",")
ALN_SEED        = os.getenv("ALN_SEED")                            # deterministic randomness if set

# ---- Table names -------------------------------------------------------------
VERSIONS_TBL   = "curriculum_versions"
REQS_TBL       = "requirements"
ALIGN_TBL      = "alignments"

# ---- Logging setup -----------------------------------------------------------
logging.getLogger("alembic.runtime.migration").setLevel(getattr(logging, LOG_LVL, logging.INFO))
engine_logger = logging.getLogger("sqlalchemy.engine")
engine_logger.setLevel(logging.INFO if LOG_SQL else getattr(logging, LOG_LVL, logging.INFO))


# ---- Helpers ----------------------------------------------------------------
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
    (Re)generate alignments.csv based on current curriculum_versions and requirements.
    Returns (path, number_of_rows_written).
    """
    out = _default_output_path(CSV_NAME)
    out.parent.mkdir(parents=True, exist_ok=True)

    insp = sa.inspect(bind)
    have_versions = insp.has_table(VERSIONS_TBL)
    have_reqs     = insp.has_table(REQS_TBL)

    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["curriculum_version_id", "requirement_id", "alignment_level", "evidence_url", "notes"])

        if not (have_versions and have_reqs):
            log.warning("[%s] Missing %s or %s; wrote header-only CSV: %s",
                        revision, VERSIONS_TBL, REQS_TBL, out)
            return out, 0

        cv_ids  = [str(r[0]) for r in bind.execute(sa.text(f"SELECT id FROM {VERSIONS_TBL} ORDER BY id")).fetchall()]
        req_ids = [str(r[0]) for r in bind.execute(sa.text(f"SELECT id FROM {REQS_TBL} ORDER BY id")).fetchall()]

        if not cv_ids or not req_ids:
            log.info("[%s] No rows to seed (cv=%d, req=%d); wrote header-only CSV: %s",
                     revision, len(cv_ids), len(req_ids), out)
            return out, 0

        rng = random.Random(ALN_SEED)
        levels = [s.strip() for s in ALN_LEVELS if s.strip()] or ["unknown"]

        rows = 0
        for cv in cv_ids:
            # choose requirements for this curriculum_version
            if ALN_PER_VERSION <= 0:
                continue
            if len(req_ids) >= ALN_PER_VERSION:
                chosen = rng.sample(req_ids, ALN_PER_VERSION)
            else:
                # cycle deterministically if fewer reqs than requested
                chosen = [req_ids[i % len(req_ids)] for i in range(ALN_PER_VERSION)]

            for req in chosen:
                level = rng.choice(levels)
                evidence_url = ""
                notes = "Seeded Alignment (alembic)"
                w.writerow([cv, req, level, evidence_url, notes])
                rows += 1

    log.info("[%s] CSV generated with %d rows => %s", revision, rows, out)
    return out, rows


def _open_csv(csv_path: Path):
    f = csv_path.open("r", encoding="utf-8", newline="")
    reader = csv.DictReader(f)
    try:
        from itertools import islice
        sample = list(islice(reader, 5))
        log.info("[%s] CSV headers: %s; first rows: %s", revision, reader.fieldnames, sample)
        f.seek(0); next(reader)  # rewind after header
    except Exception:
        pass
    return reader, f


def _insert_sql(bind):
    """
    Build an INSERT statement. If a unique (curriculum_version_id, requirement_id) exists,
    use ON CONFLICT DO NOTHING; otherwise, use a SELECT…WHERE NOT EXISTS guard.
    """
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns(ALIGN_TBL)}

    ins_cols, vals = [], []

    uuid_expr = _uuid_sql(bind)
    if "id" in cols:
        ins_cols.append("id")
        vals.append("gen_random_uuid()" if uuid_expr not in (":_uuid",) else uuid_expr)

    def add(col: str, param: Optional[str] = None):
        if col in cols:
            ins_cols.append(col)
            vals.append(f":{param or col}")

    add("curriculum_version_id")
    add("requirement_id")
    add("alignment_level")
    add("evidence_url")
    add("notes")

    # Base fragments
    cols_sql = ", ".join(ins_cols)

    # Detect a suitable unique constraint for ON CONFLICT
    uqs = {u["name"]: u for u in insp.get_unique_constraints(ALIGN_TBL)}
    uq_name = None
    for name, meta in uqs.items():
        if set(meta.get("column_names") or []) == {"curriculum_version_id", "requirement_id"}:
            uq_name = name
            break

    if bind.dialect.name == "postgresql" and uq_name:
        sql = sa.text(
            f"INSERT INTO {ALIGN_TBL} ({cols_sql}) VALUES ({', '.join(vals)}) "
            f"ON CONFLICT ON CONSTRAINT {uq_name} DO NOTHING"
        )
        needs_uuid_param = (uuid_expr == ":_uuid")
    else:
        # Portable form: INSERT … SELECT … WHERE NOT EXISTS …
        # Build a SELECT with bound params as columns
        select_list = ", ".join(vals)
        guard = (
            f" WHERE NOT EXISTS (SELECT 1 FROM {ALIGN_TBL} t "
            f"WHERE t.curriculum_version_id = :curriculum_version_id "
            f"AND t.requirement_id = :requirement_id)"
        )
        sql = sa.text(
            f"INSERT INTO {ALIGN_TBL} ({cols_sql}) SELECT {select_list}{guard}"
        )
        needs_uuid_param = (uuid_expr == ":_uuid")

    return sql, cols, needs_uuid_param


# ---- Migration ---------------------------------------------------------------
def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if not insp.has_table(ALIGN_TBL):
        log.info("[%s] Table %s missing; nothing to populate.", revision, ALIGN_TBL)
        return

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

                cv_id  = row.get("curriculum_version_id") or None
                req_id = row.get("requirement_id") or None
                level  = row.get("alignment_level") or "unknown"
                evurl  = row.get("evidence_url") or None
                notes  = row.get("notes") or None

                if not cv_id or not req_id:
                    skipped += 1
                    if LOG_ROWS:
                        log.warning("[%s] row %d missing curriculum_version_id/requirement_id — skipping: %r",
                                    revision, idx, row)
                    continue

                params = {
                    "curriculum_version_id": cv_id,
                    "requirement_id": req_id,
                    "alignment_level": level,
                    "evidence_url": evurl,
                    "notes": notes,
                }
                if needs_uuid_param and "id" in cols:
                    import uuid as _uuid
                    params["_uuid"] = str(_uuid.uuid4())

                # Keep only recognized params (plus _uuid)
                params = {k: v for k, v in params.items() if (k in cols or k == "_uuid")}

                try:
                    bind.execute(insert_stmt, params)
                    inserted += 1
                    if LOG_ROWS:
                        log.info("[%s] row %d INSERT ok (cv=%s, req=%s)", revision, idx, cv_id, req_id)
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

    if ABORT_IF_ZERO and csv_rows > 0 and inserted == 0:
        raise RuntimeError(f"[{revision}] No rows inserted; set ALN_LOG_ROWS=1 for per-row details.")


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if insp.has_table(ALIGN_TBL):
        # Best-effort removal of only the seeded rows we created
        try:
            res = bind.execute(sa.text(
                f"DELETE FROM {ALIGN_TBL} WHERE notes = 'Seeded Alignment (alembic)'"
            ))
            try:
                log.info("[%s] downgrade removed %s seeded rows from %s", revision, res.rowcount, ALIGN_TBL)
            except Exception:
                pass
        except Exception:
            log.exception("[%s] downgrade best-effort delete failed", revision)