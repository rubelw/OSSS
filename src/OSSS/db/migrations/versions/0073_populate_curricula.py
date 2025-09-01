"""Populate motions from CSV (auto-generate CSV each run, robust parsing, no manual transactions)."""

from __future__ import annotations

import os, csv, logging, random, json, traceback
from pathlib import Path
from datetime import datetime, timezone

from contextlib import nullcontext
from typing import Optional

from sqlalchemy.dialects import postgresql as pg
from alembic import op
import sqlalchemy as sa

# ---- Alembic identifiers ----
revision = "0073_populate_curricula"
down_revision = "0072_populate_proposals"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")


# ── Config / toggles (set via env) ───────────────────────────────────────────
CSV_NAME              = "curricula.csv"
SEED_COUNT            = int(os.getenv("CURRICULA_SEED_COUNT", "5"))
FIXED_ORG_ID          = os.getenv("CURRICULA_FIXED_ORG_ID", "05400000")
SEED_MARK             = "curricula_seed_v1"
CURRICULA_ABORT_IF_ZERO = os.getenv("CURRICULA_ABORT_IF_ZERO", "0") == "1"

LOG_LEVEL             = os.getenv("CURRICULA_LOG_LEVEL", "DEBUG").upper()   # DEBUG|INFO|...
LOG_SQL               = os.getenv("CURRICULA_LOG_SQL", "1") == "1"         # echo SQL logger
LOG_ROWS              = os.getenv("CURRICULA_LOG_ROWS", "1") == "1"        # per-row params
LOG_STACK             = os.getenv("CURRICULA_LOG_STACK", "1") == "1"       # include tracebacks
LOG_PEEK              = int(os.getenv("CURRICULA_LOG_PEEK", "5"))          # preview CSV rows

VALIDATE_ORG_ID       = os.getenv("CURRICULA_VALIDATE_ORG", "1") == "1"    # assert org exists
SHUFFLE_PROPOSALS     = os.getenv("CURRICULA_SHUFFLE_PROPOSALS", "1") == "1"

# ── Table names ──────────────────────────────────────────────────────────────
CURRICULA_TBL = "curricula"
PROPOSALS_TBL = "proposals"
ORGS_TBL      = "organizations"
FIXED_ORG_CODE = os.getenv("CURRICULA_FIXED_ORG_CODE", "05400000")

# ── Random pools ─────────────────────────────────────────────────────────────
SUBJECTS = ["Math", "ELA", "Science", "History", "Art", "Music", "CS"]
GRADES   = ["K-2", "3-5", "6-8", "9-12"]
STATUSES = ["draft", "adopted", "retired"]  # model default is "draft"


# ── Helpers ──────────────────────────────────────────────────────────────────
def _parse_ts(s):
    if not s:
        return None
    try:
        # handle trailing 'Z'
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def _resolve_org_id_by_code(bind, code: str) -> Optional[str]:
    """
    Return organizations.id::text for the given code.
    Fails cleanly (returns None) if the table/row is missing.
    """
    insp = sa.inspect(bind)
    if not insp.has_table(ORGS_TBL):
        log.error("[%s] Table %s not found; cannot resolve organization by code.", revision, ORGS_TBL)
        return None

    try:
        # compare on 'code' column; return UUID as text to keep everything stringly-typed for CSV
        org_id = bind.execute(
            sa.text(f"SELECT id::text FROM {ORGS_TBL} WHERE code = :code LIMIT 1"),
            {"code": code},
        ).scalar()
        if org_id:
            log.info("[%s] Resolved organization by code=%r -> id=%s", revision, code, org_id)
            return org_id
        else:
            log.error("[%s] No organization found with code=%r.", revision, code)
            return None
    except Exception as ex:
        log.error("[%s] Failed to resolve organization by code=%r: %s", revision, code, ex)
        log.debug(traceback.format_exc())
        return None

def _setup_logging():
    logging.getLogger("alembic.runtime.migration").setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
    if LOG_SQL:
        logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)

def _default_output_path(name: str) -> Path:
    return Path(__file__).resolve().with_name(name)

def _uuid_expr(bind) -> str:
    """Return SQL expr for UUID or ':_uuid' to param-inject; logs detection."""
    if bind.dialect.name != "postgresql":
        log.debug("[%s] Non-PG dialect detected; using param UUID.", revision)
        return ":_uuid"
    try:
        bind.execute(sa.text("SELECT gen_random_uuid()"))
        log.debug("[%s] Using gen_random_uuid()", revision)
        return "gen_random_uuid()"
    except Exception:
        pass
    try:
        bind.execute(sa.text("SELECT uuid_generate_v4()"))
        log.debug("[%s] Using uuid_generate_v4()", revision)
        return "uuid_generate_v4()"
    except Exception:
        pass
    log.warning("[%s] No server-side UUID function available; using param UUID.", revision)
    return ":_uuid"

def _colmap(bind, table):
    insp = sa.inspect(bind)
    return {c["name"]: c for c in insp.get_columns(table)}

def _is_timestamp(colinfo):
    # robust-ish check across dialects
    t = colinfo["type"]
    # SQLAlchemy generic
    if isinstance(t, sa.DateTime):
        return True
    # PG dialect TIMESTAMP shows up as sqlalchemy.dialects.postgresql.base.TIMESTAMP
    if t.__class__.__name__.lower() in ("timestamp", "timestamptimezone", "timestamptz"):
        return True
    # fallback string check
    return "TIMESTAMP" in str(t).upper()

def _introspect(bind):
    insp = sa.inspect(bind)
    have = {
        "curricula": insp.has_table(CURRICULA_TBL),
        "proposals": insp.has_table(PROPOSALS_TBL),
        "organizations": insp.has_table(ORGS_TBL),
    }
    log.info("[%s] Tables present: %s", revision, have)
    if have["curricula"]:
        cols = {c["name"]: c for c in insp.get_columns(CURRICULA_TBL)}
        log.info("[%s] %s columns: %s", revision, CURRICULA_TBL, sorted(cols.keys()))
    return have

def _org_exists(bind, org_id: str) -> bool:
    try:
        row = bind.execute(sa.text(f"SELECT 1 FROM {ORGS_TBL} WHERE id = :id LIMIT 1"), {"id": org_id}).fetchone()
        exists = bool(row)
        if not exists:
            log.error("[%s] Organization id %r NOT FOUND in %s — inserts will fail FK.",
                      revision, org_id, ORGS_TBL)
        else:
            log.info("[%s] Organization id %r exists — FK check OK.", revision, org_id)
        return exists
    except Exception as ex:
        log.error("[%s] Failed to check org existence: %s", revision, ex)
        if LOG_STACK:
            log.error(traceback.format_exc())
        return False

def _pick_random_proposal_ids(bind, limit: int) -> list[Optional[str]]:
    insp = sa.inspect(bind)
    if not insp.has_table(PROPOSALS_TBL):
        log.warning("[%s] Table %s missing; proposal_id will be NULL.", revision, PROPOSALS_TBL)
        return []
    rows = bind.execute(sa.text(f"SELECT id FROM {PROPOSALS_TBL}")).fetchall()
    ids = [str(r[0]) for r in rows]
    log.info("[%s] Found %d proposals; sampling up to %d.", revision, len(ids), limit)
    if SHUFFLE_PROPOSALS:
        random.shuffle(ids)
    return ids[:limit]

def _write_csv(bind, resolved_org_id: str) -> Path:
    csv_path = _default_output_path(CSV_NAME)
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    sample_props = _pick_random_proposal_ids(bind, SEED_COUNT)

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "organization_id","proposal_id","title","subject","grade_range","description",
            "attributes","name","status","published_at","metadata"
        ])
        for i in range(SEED_COUNT):
            proposal_id = sample_props[i] if i < len(sample_props) else ""
            subj  = random.choice(SUBJECTS)
            grade = random.choice(GRADES)
            status = random.choice(STATUSES)
            title = f"{subj} Curriculum {i+1}"
            name  = title
            description = f"Auto-seeded {subj} curriculum for {grade}."
            attributes = {"seed": SEED_MARK, "rand": random.randint(1, 9999)}
            metadata   = {"tags": [subj.lower(), grade], "seed": True}
            published_at = "" if status != "adopted" else "2024-08-01T00:00:00Z"

            # use the UUID we resolved from organizations.code
            w.writerow([
                resolved_org_id, proposal_id, title, subj, grade, description,
                json.dumps(attributes), name, status, published_at, json.dumps(metadata)
            ])

    # optional peek logging (kept from your version)
    try:
        with csv_path.open("r", encoding="utf-8") as f:
            lines = [next(f).rstrip("\n") for _ in range(min(1 + LOG_PEEK, SEED_COUNT + 1))]
        log.info("[%s] Wrote %s; first %d lines:\n%s", revision, csv_path, len(lines)-1, "\n".join(lines))
    except Exception:
        pass

    return csv_path

def _open_csv(csv_path: Path):
    f = csv_path.open("r", encoding="utf-8", newline="")
    reader = csv.DictReader(f)
    log.info("[%s] CSV headers: %s", revision, reader.fieldnames)
    return reader, f

def _insert_sql(bind):
    insp = sa.inspect(bind)
    cols_info = {c["name"]: c for c in insp.get_columns(CURRICULA_TBL)}
    cols = set(cols_info)

    uuid_sql = _uuid_expr(bind)
    ins_cols = ["id"]
    vals = [uuid_sql if uuid_sql != ":_uuid" else ":_uuid"]

    def add(col, param=None):
        if col in cols:
            ins_cols.append(col)
            vals.append(f":{param or col}")

    add("organization_id"); add("proposal_id"); add("title"); add("subject")
    add("grade_range"); add("description"); add("attributes")
    add("name"); add("status"); add("published_at"); add("metadata")

    # only set timestamps if the column type is actually DateTime
    def _is_dt(col):
        try:
            t = cols_info[col]["type"]
            # works across dialects
            return isinstance(t, sa.DateTime) or t.__class__.__name__.upper().startswith("TIMESTAMP")
        except KeyError:
            return False

    if "created_at" in cols and _is_dt("created_at"):
        ins_cols.append("created_at"); vals.append("now()")
    else:
        log.info("[%s] NOT setting created_at; column type is %s (expect timestamp).",
                 revision, cols_info.get("created_at", {}).get("type"))

    if "updated_at" in cols and _is_dt("updated_at"):
        ins_cols.append("updated_at"); vals.append("now()")
    else:
        log.info("[%s] NOT setting updated_at; column type is %s (expect timestamp).",
                 revision, cols_info.get("updated_at", {}).get("type"))

    sql = sa.text(
        f"INSERT INTO {CURRICULA_TBL} ({', '.join(ins_cols)}) VALUES ({', '.join(vals)})"
    ).bindparams(
        sa.bindparam("attributes", type_=sa.JSON),
        sa.bindparam("metadata",   type_=sa.JSON),
        sa.bindparam("published_at", type_=sa.DateTime(timezone=True)),
    )

    needs_uuid = (uuid_sql == ":_uuid")
    return sql, needs_uuid, cols



def _outer_tx(conn):
    try:
        if hasattr(conn, "in_transaction") and conn.in_transaction():
            return nullcontext()
    except Exception:
        return nullcontext()
    return conn.begin()

# ── Migration ────────────────────────────────────────────────────────────────
def upgrade() -> None:
    _setup_logging()
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if not insp.has_table(CURRICULA_TBL):
        raise RuntimeError(f"[{revision}] Table '{CURRICULA_TBL}' not found.")

    # NEW: resolve organization UUID by code '05400000'
    org_id = _resolve_org_id_by_code(bind, FIXED_ORG_CODE)
    if not org_id:
        raise RuntimeError(f"[{revision}] Could not resolve organization id from code={FIXED_ORG_CODE!r}")

    # regenerate CSV using the resolved UUID
    csv_path = _write_csv(bind, org_id)

    # then continue exactly as before: open CSV, build insert SQL, loop & insert
    reader, fobj = _open_csv(csv_path)
    insert_stmt, needs_uuid, cols = _insert_sql(bind)

    total = inserted = skipped = 0
    try:
        for idx, row in enumerate(reader, start=1):
            r = {k: (v.strip() if isinstance(v, str) else v) for k, v in row.items()}
            params = {
                "organization_id": r.get("organization_id") or None,
                "proposal_id": r.get("proposal_id") or None,
                "title": r.get("title") or None,
                "subject": r.get("subject") or None,
                "grade_range": r.get("grade_range") or None,
                "description": r.get("description") or None,
                "attributes": json.loads(r["attributes"]) if r.get("attributes") else None,
                "name": r.get("name") or r.get("title") or "Untitled",
                "status": (r.get("status") or "draft"),
                "published_at": _parse_ts(r.get("published_at")),
                "metadata": json.loads(r["metadata"]) if r.get("metadata") else None,
            }

            params = {k: v for k, v in params.items() if k in cols}
            if needs_uuid:
                import uuid as _uuid
                params["_uuid"] = str(_uuid.uuid4())
            try:
                bind.execute(insert_stmt, params)
                inserted += 1
            except Exception as ex:
                skipped += 1
                orig = getattr(ex, "orig", None)
                pgcode = getattr(orig, "pgcode", None)
                pgerror = getattr(orig, "pgerror", None)
                log.error(
                    "[%s] row %d INSERT failed: %r | pgcode=%s | pgerror=%s | params=%r",
                    revision, idx, ex, pgcode, pgerror, params
                )
                raise  # stop immediately to avoid InFailedSqlTransaction masking the root cause
    finally:
        try:
            fobj.close()
        except Exception:
            pass

    log.info("[%s] DONE. inserted=%d, skipped=%d, file=%s", revision, inserted, skipped, csv_path)

    if os.getenv("CURRICULA_ABORT_IF_ZERO", "0") == "1" and inserted == 0:
        raise RuntimeError(f"[{revision}] No rows inserted into {CURRICULA_TBL}.")

def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not insp.has_table(CURRICULA_TBL):
        return
    try:
        res = bind.execute(sa.text(
            f"DELETE FROM {CURRICULA_TBL} WHERE attributes::text LIKE :marker"
        ), {"marker": f'%"{SEED_MARK}"%'})
        try:
            log.info("[%s] downgrade removed %s seeded rows from %s", revision, res.rowcount, CURRICULA_TBL)
        except Exception:
            pass
    except Exception as ex:
        log.error("[%s] downgrade best-effort delete failed: %s", revision, ex)
        if LOG_STACK:
            log.error(traceback.format_exc())