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
revision = "0090_populate_projects"
down_revision = "0089_populate_contacts"  # update if needed
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

# ---- Config / env toggles ----------------------------------------------------
LOG_LVL        = os.getenv("PRJ_LOG_LEVEL", "DEBUG").upper()
LOG_SQL        = os.getenv("PRJ_LOG_SQL", "1") == "1"
LOG_ROWS       = os.getenv("PRJ_LOG_ROWS", "1") == "1"
ABORT_IF_ZERO  = os.getenv("PRJ_ABORT_IF_ZERO", "1") == "1"

CSV_ENV        = "PROJECTS_CSV_PATH"
CSV_NAME       = "projects.csv"

PRJ_PER_SCHOOL = int(os.getenv("PRJ_PER_SCHOOL", "2"))
PRJ_SEED       = os.getenv("PRJ_SEED")  # set for deterministic output

# ---- Table names -------------------------------------------------------------
SCHOOLS_TBL  = "schools"
PROJECTS_TBL = "projects"

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


def _write_csv(bind) -> tuple[Path, int]:
    """
    (Re)generate projects.csv from current schools.
    Returns (path, number_of_rows_written).
    """
    out = _default_output_path(CSV_NAME)
    out.parent.mkdir(parents=True, exist_ok=True)

    insp = sa.inspect(bind)
    if not insp.has_table(SCHOOLS_TBL):
        log.warning("[%s] Missing %s; wrote header-only CSV: %s", revision, SCHOOLS_TBL, out)
        with out.open("w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([
                "school_id","name","project_type","status",
                "start_date","end_date","budget","description","attributes"
            ])
        return out, 0

    school_ids = [str(r[0]) for r in bind.execute(sa.text(f"SELECT id FROM {SCHOOLS_TBL} ORDER BY id")).fetchall()]
    log.info("[%s] Found schools=%d", revision, len(school_ids))

    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "school_id","name","project_type","status",
            "start_date","end_date","budget","description","attributes"
        ])

        if not school_ids or PRJ_PER_SCHOOL <= 0:
            log.info("[%s] Nothing to seed (schools=%d, per_school=%d); header-only CSV written: %s",
                     revision, len(school_ids), PRJ_PER_SCHOOL, out)
            return out, 0

        rng = random.Random(PRJ_SEED)
        types = ["construction", "technology", "curriculum", "facility", "other"]
        statuses = ["planned", "active", "completed", "on_hold"]

        today = date.today()
        rows = 0
        for sid in school_ids:
            for i in range(PRJ_PER_SCHOOL):
                project_type = rng.choice(types)
                status = rng.choice(statuses)
                # dates
                start = today - timedelta(days=rng.randint(0, 365))
                if rng.random() < 0.5:
                    end = ""  # NULL
                else:
                    end = start + timedelta(days=rng.randint(30, 240))
                # budget as string to be safe for NUMERIC
                budget = f"{rng.randint(10_000, 500_000)}.{rng.randint(0,99):02d}"
                name = f"{project_type.capitalize()} Project {i+1}"
                desc = f"Seeded {project_type} project for school {sid}."

                attrs = {
                    "seeded": True,
                    "seed_revision": revision,
                    "rand": rng.randrange(1_000_000)
                }
                w.writerow([sid, name, project_type, status,
                            start.isoformat(), (end.isoformat() if end else ""),
                            budget, desc, json.dumps(attrs)])
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
        f.seek(0); next(reader)  # rewind to first data row
    except Exception:
        pass
    return reader, f


def _insert_sql(bind):
    """
    Build INSERT for projects.
    - If a unique constraint on (school_id, name) exists, use ON CONFLICT DO NOTHING.
    - Otherwise, use a portable NOT EXISTS guard on (school_id, name).
    - Pass attributes as JSON safely on Postgres.
    """
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns(PROJECTS_TBL)}

    ins_cols, vals = [], []

    uuid_expr = _uuid_sql(bind)
    if "id" in cols:
        ins_cols.append("id")
        vals.append("gen_random_uuid()" if uuid_expr not in (":_uuid",) else uuid_expr)

    def add(col: str, param: Optional[str] = None):
        if col in cols:
            ins_cols.append(col)
            vals.append(f":{param or col}")

    add("school_id")
    add("name")
    add("project_type")
    add("status")
    add("start_date")
    add("end_date")
    add("budget")
    # attributes as JSON on Postgres
    if "attributes" in cols:
        if bind.dialect.name == "postgresql":
            ins_cols.append("attributes")
            vals.append("CAST(:attributes AS JSON)")
        else:
            add("attributes")

    # Let server defaults handle created_at/updated_at if present.

    cols_sql = ", ".join(ins_cols)

    # Detect a (school_id, name) unique constraint if it exists
    uqs = {u["name"]: u for u in insp.get_unique_constraints(PROJECTS_TBL)}
    uq_name = None
    for name, meta in uqs.items():
        if set(meta.get("column_names") or []) == {"school_id", "name"}:
            uq_name = name
            break

    if bind.dialect.name == "postgresql" and uq_name:
        sql = sa.text(
            f"INSERT INTO {PROJECTS_TBL} ({cols_sql}) VALUES ({', '.join(vals)}) "
            f"ON CONFLICT ON CONSTRAINT {uq_name} DO NOTHING"
        )
        needs_uuid_param = (uuid_expr == ":_uuid")
    else:
        # Portable guard: INSERT … SELECT … WHERE NOT EXISTS …
        select_list = ", ".join(vals)
        guard = (
            f" WHERE NOT EXISTS (SELECT 1 FROM {PROJECTS_TBL} t "
            f"WHERE t.school_id = :school_id AND t.name = :name)"
        )
        sql = sa.text(f"INSERT INTO {PROJECTS_TBL} ({cols_sql}) SELECT {select_list}{guard}")
        needs_uuid_param = (uuid_expr == ":_uuid")

    log.debug("[%s] Insert SQL: %s", revision, getattr(sql, "text", str(sql)))
    return sql, cols, needs_uuid_param


# ---- Migration ---------------------------------------------------------------
def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if not insp.has_table(PROJECTS_TBL):
        log.info("[%s] Table %s missing; nothing to populate.", revision, PROJECTS_TBL)
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

                school_id   = row.get("school_id") or None
                name        = row.get("name") or None
                project_type= row.get("project_type") or None
                status      = row.get("status") or None
                start_date  = row.get("start_date") or None
                end_date    = row.get("end_date") or None
                budget      = row.get("budget") or None
                description = row.get("description") or None  # may be ignored if column absent
                attributes  = row.get("attributes") or None

                # normalize empties
                end_date = None if end_date in ("", "null", "NULL") else end_date
                budget = None if budget in ("", "null", "NULL") else budget
                attributes = None if attributes in ("", "null", "NULL") else attributes

                if not school_id or not name:
                    skipped += 1
                    if LOG_ROWS:
                        log.warning("[%s] row %d missing school_id/name — skipping: %r", revision, idx, row)
                    continue

                params = {
                    "school_id": school_id,
                    "name": name,
                    "project_type": project_type,
                    "status": status,
                    "start_date": start_date,
                    "end_date": end_date,
                    "budget": budget,
                    "attributes": attributes,
                }
                # keep only real columns (+ _uuid)
                params = {k: v for k, v in params.items() if (k in cols or k == "_uuid")}
                if needs_uuid_param and "id" in cols:
                    import uuid as _uuid
                    params["_uuid"] = str(_uuid.uuid4())

                try:
                    res = bind.execute(insert_stmt, params)
                    rc = getattr(res, "rowcount", None)
                    if rc is None:
                        rc = 1  # some drivers return None; treat as success
                    if rc > 0:
                        inserted += rc
                        if LOG_ROWS:
                            log.info("[%s] row %d INSERT ok (school=%s, name=%s, rc=%s)",
                                     revision, idx, school_id, name, rc)
                    else:
                        skipped += 1
                        if LOG_ROWS:
                            dup = bind.execute(
                                sa.text(
                                    f"SELECT 1 FROM {PROJECTS_TBL} "
                                    f"WHERE school_id = :sid AND name = :nm LIMIT 1"
                                ),
                                {"sid": school_id, "nm": name},
                            ).fetchone()
                            if dup:
                                log.info("[%s] row %d skipped (duplicate exists): (school=%s, name=%s)",
                                         revision, idx, school_id, name)
                            else:
                                log.warning("[%s] row %d skipped (no insert, no duplicate found) params=%r",
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
        raise RuntimeError(f"[{revision}] No rows inserted; set PRJ_LOG_ROWS=1 for per-row details.")


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if not insp.has_table(PROJECTS_TBL):
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
                sid = (raw.get("school_id") or "").strip()
                name = (raw.get("name") or "").strip()
                if not sid or not name:
                    continue
                try:
                    res = bind.execute(
                        sa.text(
                            f"DELETE FROM {PROJECTS_TBL} "
                            f"WHERE school_id = :sid AND name = :nm"
                        ),
                        {"sid": sid, "nm": name},
                    )
                    try:
                        deleted += res.rowcount or 0
                    except Exception:
                        pass
                except Exception:
                    if LOG_ROWS:
                        log.exception("[%s] downgrade delete failed for (school=%s, name=%s)", revision, sid, name)
    finally:
        try:
            fobj.close()
        except Exception:
            pass

    log.info("[%s] downgrade removed ~%s rows from %s (based on CSV).",
             revision, deleted, PROJECTS_TBL)