from __future__ import annotations

import os, csv, logging, random, json
from pathlib import Path
from contextlib import nullcontext
from typing import Optional

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

# ---- Alembic identifiers ----
revision = "0078_populate_activities"
down_revision = "0077_populate_accomodtns"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")


# ---- Config / env toggles ----------------------------------------------------
LOG_LVL        = os.getenv("ACT_LOG_LEVEL", "INFO").upper()
LOG_SQL        = os.getenv("ACT_LOG_SQL", "1") == "1"
LOG_ROWS       = os.getenv("ACT_LOG_ROWS", "1") == "1"
ABORT_IF_ZERO  = os.getenv("ACT_ABORT_IF_ZERO", "1") == "1"

CSV_ENV        = "ACTIVITIES_CSV_PATH"  # can be a file path or a directory
CSV_NAME       = "activities.csv"

# Rows per school (default: 1). If you want more, set ACT_PER_SCHOOL=3, etc.
ACT_PER_SCHOOL = int(os.getenv("ACT_PER_SCHOOL", "1"))
ACT_SEED       = os.getenv("ACT_SEED")  # for deterministic names if desired

# ---- Table names -------------------------------------------------------------
SCHOOLS_TBL    = "schools"
ACTIVITIES_TBL = "activities"

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
    Always (re)write activities.csv with ACT_PER_SCHOOL rows per school.
    Columns: school_id, name, description, is_active
    """
    out = _default_output_path(CSV_NAME)
    out.parent.mkdir(parents=True, exist_ok=True)

    insp = sa.inspect(bind)
    if not insp.has_table(SCHOOLS_TBL):
        log.warning("[%s] Table %s not found; writing header-only CSV.", revision, SCHOOLS_TBL)
        with out.open("w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(["school_id", "name", "description", "is_active"])
        return out, 0

    rows = bind.execute(sa.text(f"SELECT id FROM {SCHOOLS_TBL} ORDER BY id")).fetchall()
    school_ids = [str(r[0]) for r in rows]

    rng = random.Random(ACT_SEED)

    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["school_id", "name", "description", "is_active"])
        for sid in school_ids:
            for n in range(1, ACT_PER_SCHOOL + 1):
                # Simple seeded names; adjust if you like
                suffix = f"{n}" if ACT_PER_SCHOOL > 1 else ""
                name = f"Seeded Activity{(' ' + suffix) if suffix else ''}"
                description = "Seeded activity for testing"
                # Model maps is_active to a TEXT column with default "1". We’ll write "1".
                is_active = "1"
                # Slight variety if seed provided:
                if ACT_SEED:
                    variants = ["Drama Club", "Robotics", "Soccer", "Chess", "Debate"]
                    name = rng.choice(variants) + (f" {suffix}" if suffix else "")
                    description = f"Seeded activity ({name})"
                w.writerow([sid, name, description, is_active])

    log.info("[%s] CSV generated with %d school(s) × %d activities => %s",
             revision, len(school_ids), ACT_PER_SCHOOL, out)
    return out, len(school_ids)


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
    Build INSERT that avoids duplicates:
      - If a unique constraint exists on (school_id, name), use ON CONFLICT DO NOTHING (Postgres).
      - Else do INSERT … SELECT … WHERE NOT EXISTS … with NULL-safety where possible.
    """
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns(ACTIVITIES_TBL)}

    insert_cols: list[str] = []
    select_vals: list[str] = []

    uuid_expr = _uuid_sql(bind)
    insert_cols.append("id")
    select_vals.append(uuid_expr if uuid_expr != ":_uuid" else ":_uuid")

    def add(col: str, param: Optional[str] = None):
        if col in cols:
            insert_cols.append(col)
            select_vals.append(f":{param or col}")

    add("school_id")
    add("name")
    add("description")
    add("is_active")  # TEXT, defaults to "1"; we pass through if present

    # If created_at/updated_at exist, set to now()
    if "created_at" in cols:
        insert_cols.append("created_at")
        select_vals.append("now()")
    if "updated_at" in cols:
        insert_cols.append("updated_at")
        select_vals.append("now()")

    col_list = ", ".join(insert_cols)
    select_list = ", ".join(select_vals)

    # Try to discover a unique constraint we can target
    uqs = {u["name"]: u for u in insp.get_unique_constraints(ACTIVITIES_TBL)}
    conflict_name = None
    for name, u in uqs.items():
        cset = set(u.get("column_names") or [])
        if {"school_id", "name"}.issubset(cset):
            conflict_name = name
            break

    if bind.dialect.name == "postgresql" and conflict_name:
        sql = sa.text(
            f"INSERT INTO {ACTIVITIES_TBL} ({col_list}) "
            f"VALUES ({select_list}) "
            f"ON CONFLICT ON CONSTRAINT {conflict_name} DO NOTHING"
        )
    else:
        # Portable NOT EXISTS guard (Postgres gets clean syntax + NULL-safe school_id)
        if bind.dialect.name == "postgresql":
            guard = (
                f" WHERE NOT EXISTS ("
                f"SELECT 1 FROM {ACTIVITIES_TBL} "
                f"WHERE name = :name "
                f"AND school_id IS NOT DISTINCT FROM :school_id)"
            )
        else:
            guard = (
                f" WHERE NOT EXISTS ("
                f"SELECT 1 FROM {ACTIVITIES_TBL} "
                f"WHERE name = :name "
                f"AND ((school_id = :school_id) OR (school_id IS NULL AND :school_id IS NULL)))"
            )
        sql = sa.text(
            f"INSERT INTO {ACTIVITIES_TBL} ({col_list}) "
            f"SELECT {select_list}{guard}"
        )

    needs_uuid_param = (uuid_expr == ":_uuid")
    return sql, cols, needs_uuid_param


# ---- Migration ---------------------------------------------------------------
def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if not insp.has_table(ACTIVITIES_TBL):
        log.info("[%s] Table %s missing; nothing to populate.", revision, ACTIVITIES_TBL)
        return

    csv_path, school_count = _write_csv(bind)
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

                school_id   = row.get("school_id") or None  # may be empty -> NULL
                name        = row.get("name") or None
                description = row.get("description") or None
                is_active   = row.get("is_active") or None  # keep as text; model column is TEXT

                if not name:
                    skipped += 1
                    if LOG_ROWS:
                        log.warning("[%s] row %d missing 'name' — skipping: %r", revision, idx, row)
                    continue

                params = {
                    "school_id": school_id,
                    "name": name,
                    "description": description,
                    "is_active": is_active,
                }
                if needs_uuid_param:
                    import uuid as _uuid
                    params["_uuid"] = str(_uuid.uuid4())

                # Keep only params that match real columns (+ _uuid)
                params = {k: v for k, v in params.items() if (k in cols or k == "_uuid")}

                try:
                    bind.execute(insert_stmt, params)
                    inserted += 1
                    if LOG_ROWS:
                        log.info("[%s] row %d INSERT ok (school_id=%s, name=%s)",
                                 revision, idx, school_id, name)
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

    if ABORT_IF_ZERO and school_count > 0 and inserted == 0:
        raise RuntimeError(f"[{revision}] No rows inserted; set ACT_LOG_ROWS=1 for per-row details.")


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if insp.has_table(ACTIVITIES_TBL):
        try:
            # Best-effort delete of seeded rows (by our conventional description/name)
            res = bind.execute(sa.text(
                f"DELETE FROM {ACTIVITIES_TBL} "
                f"WHERE description LIKE 'Seeded activity%' OR name LIKE 'Seeded Activity%%'"
            ))
            try:
                log.info("[%s] downgrade removed %s seeded rows from %s",
                         revision, res.rowcount, ACTIVITIES_TBL)
            except Exception:
                pass
        except Exception:
            log.exception("[%s] downgrade best-effort delete failed", revision)