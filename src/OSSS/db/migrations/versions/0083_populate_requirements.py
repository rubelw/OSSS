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
revision = "0083_populate_requirements"
down_revision = "0082_populate_agenda_it_f"  # update if needed
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

# ---- Config / env toggles ----------------------------------------------------
LOG_LVL        = os.getenv("REQ_LOG_LEVEL", "DEBUG").upper()
LOG_SQL        = os.getenv("REQ_LOG_SQL", "1") == "1"
LOG_ROWS       = os.getenv("REQ_LOG_ROWS", "1") == "1"
ABORT_IF_ZERO  = os.getenv("REQ_ABORT_IF_ZERO", "1") == "1"

CSV_ENV        = "REQUIREMENTS_CSV_PATH"  # dir or full file path
CSV_NAME       = "requirements.csv"

# How many requirements to create per state (default 1)
REQS_PER_STATE = max(1, int(os.getenv("REQS_PER_STATE", "1")))
REQ_SEED       = os.getenv("REQ_SEED")

# ---- Table names / constraint -----------------------------------------------
STATES_TBL = "states"
TARGET_TBL = "requirements"
UQ_NAME    = "uq_requirements_state_title"   # we’ll ensure (state_code, title) is unique

# ---- Logging setup -----------------------------------------------------------
logging.getLogger("alembic.runtime.migration").setLevel(getattr(logging, LOG_LVL, logging.INFO))
_engine_logger = logging.getLogger("sqlalchemy.engine")
_engine_logger.setLevel(logging.INFO if LOG_SQL else getattr(logging, LOG_LVL, logging.INFO))


# ---- Helpers ----------------------------------------------------------------
def _outer_tx(conn):
    """Return a context manager that opens a transaction only if one isn't active."""
    try:
        # SA 1.4 / 2.x
        if hasattr(conn, "in_transaction") and conn.in_transaction():
            return nullcontext()
        # Older patterns
        if hasattr(conn, "get_transaction") and conn.get_transaction() is not None:
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


def _ensure_unique_constraint(bind):
    """Ensure (state_code, title) unique exists for clean ON CONFLICT semantics."""
    insp = sa.inspect(bind)
    if not insp.has_table(TARGET_TBL):
        return
    uqs = {u["name"]: u for u in insp.get_unique_constraints(TARGET_TBL)}
    desired_cols = ["state_code", "title"]
    if UQ_NAME in uqs and uqs[UQ_NAME]["column_names"] != desired_cols:
        op.drop_constraint(UQ_NAME, TARGET_TBL, type_="unique")
    if UQ_NAME not in uqs or uqs[UQ_NAME]["column_names"] != desired_cols:
        try:
            op.create_unique_constraint(UQ_NAME, TARGET_TBL, desired_cols)
        except Exception:
            # another head may already have created it; ignore
            pass


def _write_csv(bind) -> tuple[Path, int]:
    """
    Always (re)write requirements.csv from current states.
    Returns (path, number_of_states).
    """
    out = _default_output_path(CSV_NAME)
    out.parent.mkdir(parents=True, exist_ok=True)

    insp = sa.inspect(bind)
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "state_code", "title", "category", "description",
            "effective_date", "reference_url", "attributes"
        ])

        if not insp.has_table(STATES_TBL):
            log.warning("[%s] Table %s not found; wrote header-only CSV: %s",
                        revision, STATES_TBL, out)
            return out, 0

        rows = bind.execute(sa.text(f"SELECT code FROM {STATES_TBL} ORDER BY code")).fetchall()
        codes = [str(r[0]) for r in rows]
        if not codes:
            log.warning("[%s] No states present; wrote header-only CSV: %s", revision, out)
            return out, 0

        rng = random.Random(REQ_SEED)
        for code in codes:
            for i in range(1, REQS_PER_STATE + 1):
                title = f"Seeded Requirement {i} for {code}"
                category = rng.choice(["General", "Assessment", "Curriculum", "Reporting"])
                description = f"Seeded requirement row {i} for {code} (alembic)."
                effective_date = ""   # empty -> NULL
                reference_url = ""    # optional
                attributes = json.dumps({"seeded": True, "seed_revision": revision})
                w.writerow([code, title, category, description, effective_date, reference_url, attributes])

    log.info("[%s] CSV generated with %d states × %d reqs/state => %s",
             revision, len(codes), REQS_PER_STATE, out)
    return out, len(codes)


def _open_csv(csv_path: Path):
    f = csv_path.open("r", encoding="utf-8", newline="")
    reader = csv.DictReader(f)
    log.info("[%s] CSV headers: %s", revision, reader.fieldnames)
    # peek
    try:
        from itertools import islice
        preview = list(islice(reader, 5))
        log.info("[%s] First rows preview: %s", revision, preview)
        f.seek(0); next(reader)
    except Exception:
        pass
    return reader, f


from sqlalchemy.dialects import postgresql as pg

def _insert_sql(bind):
    """Build parametrized INSERT, handling JSON/JSONB casting and idempotence.
    NOTE: We never set created_at/updated_at here (some schemas use tsvector with those names)."""
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns(TARGET_TBL)}

    # detect JSON vs JSONB for 'attributes'
    cols_info = insp.get_columns(TARGET_TBL)
    attr_is_jsonb = any(
        c["name"] == "attributes" and isinstance(c["type"], pg.JSONB)
        for c in cols_info
    )

    insert_cols: list[str] = []
    value_exprs: list[str] = []
    select_exprs: list[str] = []

    def add(col: str, param: Optional[str] = None, expr_override: Optional[str] = None):
        if col in cols:
            insert_cols.append(col)
            expr = expr_override or f":{param or col}"
            value_exprs.append(expr)
            select_exprs.append(expr)

    # required/known columns
    add("state_code")
    add("title")
    add("category")
    add("description")
    add("effective_date")
    add("reference_url")

    # JSON / JSONB
    if "attributes" in cols:
        if bind.dialect.name == "postgresql":
            cast_type = "JSONB" if attr_is_jsonb else "JSON"
            add("attributes", "attributes", f"CAST(:attributes AS {cast_type})")
        else:
            add("attributes")

    # DO NOT auto-set created_at / updated_at here — some schemas map these names to tsvector.
    # If your table has timestamp defaults, they’ll fill in automatically.

    col_list = ", ".join(insert_cols)

    # Prefer ON CONFLICT when the unique constraint exists
    if bind.dialect.name == "postgresql":
        uqs = {u["name"]: u for u in insp.get_unique_constraints(TARGET_TBL)}
        if UQ_NAME in uqs:
            return sa.text(
                f"INSERT INTO {TARGET_TBL} ({col_list}) "
                f"VALUES ({', '.join(value_exprs)}) "
                f"ON CONFLICT ON CONSTRAINT {UQ_NAME} DO NOTHING"
            ), cols

    # Generic fallback: INSERT ... SELECT ... WHERE NOT EXISTS
    where = (
        f" WHERE NOT EXISTS (SELECT 1 FROM {TARGET_TBL} t "
        f"WHERE t.state_code = :state_code AND t.title = :title)"
    )
    stmt = sa.text(
        f"INSERT INTO {TARGET_TBL} ({col_list}) "
        f"SELECT {', '.join(select_exprs)}{where}"
    )
    return stmt, cols

# ---- Migration ---------------------------------------------------------------
def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if not insp.has_table(TARGET_TBL):
        log.info("[%s] Table %s missing; nothing to populate.", revision, TARGET_TBL)
        return

    _ensure_unique_constraint(bind)

    csv_path, states_count = _write_csv(bind)
    reader, fobj = _open_csv(csv_path)

    insert_stmt, cols = _insert_sql(bind)

    total = inserted = skipped = 0

    with _outer_tx(bind):
        for idx, raw in enumerate(reader, start=1):
            total += 1
            if not raw:
                continue

            row = {(k.strip() if isinstance(k, str) else k): (v.strip() if isinstance(v, str) else v)
                   for k, v in raw.items()}

            state_code = row.get("state_code") or None
            title = row.get("title") or None
            category = row.get("category") or None
            description = row.get("description") or None
            effective_date = row.get("effective_date") or None
            reference_url = row.get("reference_url") or None
            attributes = row.get("attributes") or None

            if not state_code or not title:
                skipped += 1
                if LOG_ROWS:
                    log.warning("[%s] row %d missing state_code/title — skipping: %r", revision, idx, row)
                continue

            # normalize blanks
            effective_date = None if effective_date in ("", "null", "NULL") else effective_date
            reference_url = None if reference_url in ("", "null", "NULL") else reference_url
            attributes = None if attributes in ("", "null", "NULL") else attributes

            params = {
                "state_code": state_code,
                "title": title,
                "category": category,
                "description": description,
                "effective_date": effective_date,
                "reference_url": reference_url,
                "attributes": attributes,
            }
            # keep only valid params for detected columns (you already computed `cols`)
            params = {k: v for k, v in params.items() if k in cols}

            try:
                bind.execute(insert_stmt, params)
                inserted += 1
                if LOG_ROWS:
                    log.info("[%s] row %d INSERT ok (state=%s title=%s)", revision, idx, state_code, title)
            except Exception:
                skipped += 1
                if LOG_ROWS:
                    log.exception("[%s] row %d INSERT failed; params=%r", revision, idx, params)

    log.info("[%s] CSV rows=%d, inserted=%d, skipped=%d (file=%s)",
             revision, total, inserted, skipped, csv_path)

    if ABORT_IF_ZERO and states_count > 0 and inserted == 0:
        raise RuntimeError(f"[{revision}] No rows inserted; set REQ_LOG_ROWS=1 for per-row details.")


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not insp.has_table(TARGET_TBL):
        return
    # Prefer targeted cleanup using seed marker in attributes (Postgres path)
    try:
        if bind.dialect.name == "postgresql":
            res = bind.execute(sa.text(
                f"DELETE FROM {TARGET_TBL} WHERE attributes->>'seed_revision' = :rev"
            ), {"rev": revision})
        else:
            # Generic best-effort cleanup by title prefix
            res = bind.execute(sa.text(
                f"DELETE FROM {TARGET_TBL} WHERE title LIKE 'Seeded Requirement %'"
            ))
        try:
            log.info("[%s] downgrade removed %s seeded rows from %s", revision, res.rowcount, TARGET_TBL)
        except Exception:
            pass
    except Exception:
        log.exception("[%s] downgrade best-effort delete failed", revision)