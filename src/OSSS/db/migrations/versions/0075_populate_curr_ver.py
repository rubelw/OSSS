from __future__ import annotations

import os, csv, logging, random, json
from pathlib import Path
from contextlib import nullcontext
from typing import Optional

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

# ---- Alembic identifiers ----
revision = "0075_populate_curriculum_ver"
down_revision = "0074_populate_curr_units"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

# ---- Config / env toggles ----------------------------------------------------
LOG_LVL        = os.getenv("CV_LOG_LEVEL", "INFO").upper()
LOG_SQL        = os.getenv("CV_LOG_SQL", "1") == "1"
LOG_ROWS       = os.getenv("CV_LOG_ROWS", "1") == "1"
ABORT_IF_ZERO  = os.getenv("CV_ABORT_IF_ZERO", "1") == "1"

CSV_ENV        = "CURRICULUM_VERSIONS_CSV_PATH"
CSV_NAME       = "curriculum_versions.csv"

CV_VERSIONS_PER_CURR = int(os.getenv("CV_VERSIONS_PER_CURR", "1"))
CV_SEED              = os.getenv("CV_SEED")

# ---- Table names -------------------------------------------------------------
CURRICULA_TBL  = "curricula"
VERSIONS_TBL   = "curriculum_versions"

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


def _ensure_schema(bind):
    insp = sa.inspect(bind)

    if not insp.has_table(VERSIONS_TBL):
        log.info("[%s] Table %s missing; nothing to populate.", revision, VERSIONS_TBL)
        return

    # unique(curriculum_id, version) for ON CONFLICT
    uqs = {u["name"]: u for u in insp.get_unique_constraints(VERSIONS_TBL)}
    desired_cols = ["curriculum_id", "version"]
    if "uq_cv_curr_version" in uqs and uqs["uq_cv_curr_version"]["column_names"] != desired_cols:
        op.drop_constraint("uq_cv_curr_version", VERSIONS_TBL, type_="unique")
    if "uq_cv_curr_version" not in uqs or (
        "uq_cv_curr_version" in uqs and uqs["uq_cv_curr_version"]["column_names"] != desired_cols
    ):
        try:
            op.create_unique_constraint("uq_cv_curr_version", VERSIONS_TBL, desired_cols)
        except Exception:
            pass


def _write_csv(bind) -> tuple[Path, int]:
    """
    Always (re)write curriculum_versions.csv.
    Returns (path, number_of_curricula).
    """
    out = _default_output_path(CSV_NAME)
    out.parent.mkdir(parents=True, exist_ok=True)

    insp = sa.inspect(bind)
    if not insp.has_table(CURRICULA_TBL):
        log.warning("[%s] Table %s not found; writing header-only CSV.", revision, CURRICULA_TBL)
        with out.open("w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(["curriculum_id", "version", "status", "submitted_at", "decided_at", "notes"])
        return out, 0

    rows = bind.execute(sa.text(f"SELECT id FROM {CURRICULA_TBL} ORDER BY id")).fetchall()
    cur_ids = [str(r[0]) for r in rows]

    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["curriculum_id", "version", "status", "submitted_at", "decided_at", "notes"])

        if not cur_ids:
            log.warning("[%s] No curricula present; header-only CSV written: %s", revision, out)
            return out, 0

        rng = random.Random(CV_SEED)
        for cid in cur_ids:
            for v in range(1, CV_VERSIONS_PER_CURR + 1):
                # Basic seed: draft versions v1..vN, no timestamps
                version = f"v{v}"
                status = "draft"
                submitted_at = ""   # empty -> NULL
                decided_at = ""     # empty -> NULL
                notes = "Seeded Curriculum Version"
                w.writerow([cid, version, status, submitted_at, decided_at, notes])

    log.info("[%s] CSV generated with %d curriculum × %d versions => %s",
             revision, len(cur_ids), CV_VERSIONS_PER_CURR, out)
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

def _is_timestamp(coltype) -> bool:
    """True if column type is a SQLAlchemy DateTime (with/without tz)."""
    from sqlalchemy.sql.sqltypes import DateTime
    try:
        return isinstance(coltype, DateTime)
    except Exception:
        return False


def _insert_sql(bind):
    insp = sa.inspect(bind)
    cols_info = {c["name"]: c for c in insp.get_columns(VERSIONS_TBL)}
    cols = set(cols_info)

    ins_cols, vals = [], []

    uuid_expr = _uuid_sql(bind)
    if uuid_expr == ":_uuid":
        ins_cols.append("id"); vals.append(":_uuid")
    else:
        ins_cols.append("id"); vals.append(uuid_expr)

    def add(col: str, param: Optional[str] = None):
        if col in cols:
            ins_cols.append(col)
            vals.append(f":{param or col}")

    # regular data columns
    add("curriculum_id")
    add("version")
    add("status")
    add("submitted_at")
    add("decided_at")
    add("notes")

    # only set timestamps if their types are actually DateTime
    if "created_at" in cols and _is_timestamp(cols_info["created_at"]["type"]):
        ins_cols.append("created_at"); vals.append("now()")
    if "updated_at" in cols and _is_timestamp(cols_info["updated_at"]["type"]):
        ins_cols.append("updated_at"); vals.append("now()")

    base_sql = f"INSERT INTO {VERSIONS_TBL} ({', '.join(ins_cols)}) VALUES ({', '.join(vals)})"

    # Use ON CONFLICT if unique exists; otherwise NOT EXISTS guard
    uqs = {u["name"]: u for u in insp.get_unique_constraints(VERSIONS_TBL)}
    if bind.dialect.name == "postgresql" and "uq_cv_curr_version" in uqs:
        sql = sa.text(base_sql + " ON CONFLICT ON CONSTRAINT uq_cv_curr_version DO NOTHING")
    else:
        guard = (
            f" WHERE NOT EXISTS (SELECT 1 FROM {VERSIONS_TBL} "
            f"WHERE curriculum_id = :curriculum_id AND version = :version)"
        )
        sql = sa.text(base_sql + guard)

    return sql, cols, (uuid_expr == ":_uuid")

# ---- Migration ---------------------------------------------------------------
def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    _ensure_schema(bind)

    if not insp.has_table(VERSIONS_TBL):
        log.info("[%s] Table %s missing; nothing to populate.", revision, VERSIONS_TBL)
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
                version       = row.get("version") or None
                status        = row.get("status") or None
                submitted_at  = row.get("submitted_at") or None
                decided_at    = row.get("decided_at") or None
                notes         = row.get("notes") or None

                if not curriculum_id or not version:
                    skipped += 1
                    if LOG_ROWS:
                        log.warning("[%s] row %d missing curriculum_id/version — skipping: %r", revision, idx, row)
                    continue

                # Normalize empty timestamps to NULL
                submitted_at = None if (submitted_at in ("", "null", "NULL")) else submitted_at
                decided_at   = None if (decided_at   in ("", "null", "NULL")) else decided_at

                params = {
                    "curriculum_id": curriculum_id,
                    "version": version,
                    "status": status or "draft",
                    "submitted_at": submitted_at,
                    "decided_at": decided_at,
                    "notes": notes,
                }
                if needs_uuid_param:
                    import uuid as _uuid
                    params["_uuid"] = str(_uuid.uuid4())

                # Keep only params that match real columns (plus _uuid)
                params = {k: v for k, v in params.items() if (k in cols or k == "_uuid")}

                try:
                    bind.execute(insert_stmt, params)
                    inserted += 1
                    if LOG_ROWS:
                        log.info("[%s] row %d INSERT ok (curriculum_id=%s, version=%s)",
                                 revision, idx, curriculum_id, version)
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

    if ABORT_IF_ZERO and curricula_count > 0 and inserted == 0:
        raise RuntimeError(f"[{revision}] No rows inserted; set CV_LOG_ROWS=1 for per-row details.")


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if insp.has_table(VERSIONS_TBL):
        try:
            res = bind.execute(sa.text(
                f"DELETE FROM {VERSIONS_TBL} WHERE notes = 'Seeded Curriculum Version'"
            ))
            try:
                log.info("[%s] downgrade removed %s seeded rows from %s", revision, res.rowcount, VERSIONS_TBL)
            except Exception:
                pass
        except Exception:
            log.exception("[%s] downgrade best-effort delete failed", revision)