# src/OSSS/db/migrations/versions/0081_populate_audit_logs.py
from __future__ import annotations

import os, csv, json, logging, uuid, random, re
from pathlib import Path
from contextlib import nullcontext
from typing import Optional
from datetime import date, timedelta


from alembic import op
import sqlalchemy as sa

# ---- Alembic identifiers ----
revision = "0091_populate_immuniztns"
down_revision = "0090_populate_projects"  # update if needed
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")


# ---- Config / env toggles ----------------------------------------------------
LOG_LVL        = os.getenv("IMM_LOG_LEVEL", "INFO").upper()
LOG_SQL        = os.getenv("IMM_LOG_SQL", "1") == "1"
LOG_ROWS       = os.getenv("IMM_LOG_ROWS", "1") == "1"
ABORT_IF_ZERO  = os.getenv("IMM_ABORT_IF_ZERO", "1") == "1"

CSV_ENV        = "IMMUNIZATIONS_CSV_PATH"
# Default filename honors your request; override via IMMUNIZATIONS_CSV_NAME if desired
CSV_NAME       = os.getenv("IMMUNIZATIONS_CSV_NAME", "immunications.csv")

TABLE_NAME     = "immunizations"

# ---- Logging setup -----------------------------------------------------------
logging.getLogger("alembic.runtime.migration").setLevel(getattr(logging, LOG_LVL, logging.INFO))
_engine_logger = logging.getLogger("sqlalchemy.engine")
_engine_logger.setLevel(logging.INFO if LOG_SQL else getattr(logging, LOG_LVL, logging.INFO))


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


# Canonical school immunizations (name, code). Codes use common abbreviations.
_IMM_ROWS: list[tuple[str, Optional[str]]] = [
    ("DTaP (Diphtheria, Tetanus, acellular Pertussis)", "DTaP"),
    ("Tdap (Tetanus, diphtheria, acellular Pertussis)", "Tdap"),
    ("Polio (IPV)", "IPV"),
    ("MMR (Measles, Mumps, Rubella)", "MMR"),
    ("Varicella (Chickenpox)", "VAR"),
    ("Hepatitis B", "HepB"),
    ("Hepatitis A", "HepA"),
    ("Hib (Haemophilus influenzae type b)", "Hib"),
    ("Pneumococcal Conjugate", "PCV"),
    ("Meningococcal ACWY", "MCV4"),
    ("HPV (Human Papillomavirus)", "HPV"),
    ("Influenza (Seasonal)", "Flu"),
]


def _write_csv() -> tuple[Path, int]:
    """
    (Re)generate immunizations CSV with standard school immunizations.
    Returns (path, number_of_rows_written).
    """
    out = _default_output_path(CSV_NAME)
    out.parent.mkdir(parents=True, exist_ok=True)

    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["name", "code"])
        for name, code in _IMM_ROWS:
            w.writerow([name, code or ""])

    log.info("[%s] CSV generated with %d rows => %s", revision, len(_IMM_ROWS), out)
    return out, len(_IMM_ROWS)


def _open_csv(csv_path: Path):
    f = csv_path.open("r", encoding="utf-8", newline="")
    reader = csv.DictReader(f)
    try:
        from itertools import islice
        sample = list(islice(reader, 5))
        log.info("[%s] CSV headers: %s; first rows: %s", revision, reader.fieldnames, sample)
        f.seek(0); next(reader)  # rewind to first data row
    except Exception:
        pass
    return reader, f


def _insert_sql(bind):
    """
    Build INSERT for immunizations.
    - If a unique constraint on (name) or (name, code) exists, use ON CONFLICT DO NOTHING.
    - Otherwise, use a portable NOT EXISTS guard on (name, COALESCE(code,'')).
    - We do NOT set created_at/updated_at explicitly; let server defaults handle them.
    """
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns(TABLE_NAME)}

    ins_cols, vals = [], []

    uuid_expr = _uuid_sql(bind)
    if "id" in cols:
        ins_cols.append("id")
        vals.append("gen_random_uuid()" if uuid_expr not in (":_uuid",) else uuid_expr)

    def add(col: str, param: Optional[str] = None):
        if col in cols:
            ins_cols.append(col)
            vals.append(f":{param or col}")

    add("name")
    add("code")

    cols_sql = ", ".join(ins_cols)

    # Detect suitable unique constraint
    uqs = {u["name"]: u for u in insp.get_unique_constraints(TABLE_NAME)}
    uq_name = None
    for name, meta in uqs.items():
        cols_set = set(meta.get("column_names") or [])
        if cols_set == {"name"} or cols_set == {"name", "code"}:
            uq_name = name
            break

    if bind.dialect.name == "postgresql" and uq_name:
        sql = sa.text(
            f"INSERT INTO {TABLE_NAME} ({cols_sql}) VALUES ({', '.join(vals)}) "
            f"ON CONFLICT ON CONSTRAINT {uq_name} DO NOTHING"
        )
        needs_uuid_param = (uuid_expr == ":_uuid")
    else:
        # Portable guard: consider name + code (NULL-safe via COALESCE)
        select_list = ", ".join(vals)
        guard = (
            f" WHERE NOT EXISTS (SELECT 1 FROM {TABLE_NAME} t "
            f"WHERE t.name = :name AND COALESCE(t.code,'') = COALESCE(:code,''))"
        )
        sql = sa.text(f"INSERT INTO {TABLE_NAME} ({cols_sql}) SELECT {select_list}{guard}")
        needs_uuid_param = (uuid_expr == ":_uuid")

    log.debug("[%s] Insert SQL: %s", revision, getattr(sql, "text", str(sql)))
    return sql, cols, needs_uuid_param


# ---- Migration ---------------------------------------------------------------
def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if not insp.has_table(TABLE_NAME):
        log.info("[%s] Table %s missing; nothing to populate.", revision, TABLE_NAME)
        return

    csv_path, csv_rows = _write_csv()
    reader, fobj = _open_csv(csv_path)

    insert_stmt, cols, needs_uuid_param = _insert_sql(bind)

    total = inserted = skipped = 0
    try:
        with _outer_tx(bind):
            for idx, raw in enumerate(reader, start=1):
                total += 1
                if not raw:
                    continue
                name = (raw.get("name") or "").strip()
                code = (raw.get("code") or "").strip() or None

                if not name:
                    skipped += 1
                    if LOG_ROWS:
                        log.warning("[%s] row %d missing name — skipping: %r", revision, idx, raw)
                    continue

                params = {"name": name, "code": code}
                params = {k: v for k, v in params.items() if (k in cols or k == "_uuid")}
                if needs_uuid_param and "id" in cols:
                    import uuid as _uuid
                    params["_uuid"] = str(_uuid.uuid4())

                try:
                    res = bind.execute(insert_stmt, params)
                    rc = getattr(res, "rowcount", None)
                    if rc is None:
                        rc = 1
                    if rc > 0:
                        inserted += rc
                        if LOG_ROWS:
                            log.info("[%s] row %d INSERT ok (name=%s, code=%s, rc=%s)",
                                     revision, idx, name, code, rc)
                    else:
                        skipped += 1
                        if LOG_ROWS:
                            dup = bind.execute(
                                sa.text(
                                    f"SELECT 1 FROM {TABLE_NAME} "
                                    f"WHERE name = :nm AND COALESCE(code,'') = COALESCE(:cd,'') LIMIT 1"
                                ),
                                {"nm": name, "cd": code or ""},
                            ).fetchone()
                            if dup:
                                log.info("[%s] row %d skipped (duplicate): name=%s code=%s",
                                         revision, idx, name, code)
                            else:
                                log.warning("[%s] row %d skipped (no insert, no dup found) params=%r",
                                            revision, idx, params)
                except Exception:
                    skipped += 1
                    if LOG_ROWS:
                        log.exception("[%s] row %d INSERT failed; params=%r", revision, idx, params)
    finally:
        try:
            fobj.close()
        except Exception:
            pass

    log.info("[%s] CSV rows=%d, attempted=%d, inserted=%d, skipped=%d (file=%s)",
             revision, csv_rows, total, inserted, skipped, csv_path)

    if ABORT_IF_ZERO and csv_rows > 0 and inserted == 0:
        raise RuntimeError(f"[{revision}] No rows inserted; set IMM_LOG_ROWS=1 for per-row details.")


def downgrade() -> None:
    """Best-effort delete using the CSV names/codes written by this revision."""
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if not insp.has_table(TABLE_NAME):
        return

    csv_path = _default_output_path(CSV_NAME)
    if not csv_path.exists():
        log.info("[%s] downgrade: CSV %s not found; skipping delete.", revision, csv_path)
        return

    reader, fobj = _open_csv(csv_path)
    deleted = 0
    try:
        with _outer_tx(bind):
            for raw in reader:
                name = (raw.get("name") or "").strip()
                code = (raw.get("code") or "").strip()
                try:
                    res = bind.execute(
                        sa.text(
                            f"DELETE FROM {TABLE_NAME} "
                            f"WHERE name = :nm AND COALESCE(code,'') = COALESCE(:cd,'')"
                        ),
                        {"nm": name, "cd": code},
                    )
                    try:
                        deleted += res.rowcount or 0
                    except Exception:
                        pass
                except Exception:
                    if LOG_ROWS:
                        log.exception("[%s] downgrade delete failed for name=%s code=%s", revision, name, code)
    finally:
        try:
            fobj.close()
        except Exception:
            pass

    log.info("[%s] downgrade removed ~%s rows from %s (based on CSV).",
             revision, deleted, TABLE_NAME)