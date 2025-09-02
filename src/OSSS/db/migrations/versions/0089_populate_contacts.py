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
revision = "0089_populate_contacts"
down_revision = "0088_populate_section_mtg"  # update if needed
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")


# ---- Config / env toggles ----------------------------------------------------
LOG_LVL        = os.getenv("CNT_LOG_LEVEL", "INFO").upper()
LOG_SQL        = os.getenv("CNT_LOG_SQL", "1") == "1"
LOG_ROWS       = os.getenv("CNT_LOG_ROWS", "1") == "1"
ABORT_IF_ZERO  = os.getenv("CNT_ABORT_IF_ZERO", "1") == "1"

CSV_ENV        = "CONTACTS_CSV_PATH"
CSV_NAME       = "contacts.csv"

# generation knobs
CNT_PER_SCHOOL = int(os.getenv("CNT_PER_SCHOOL", "3"))  # contacts per school if schools table exists
CNT_FALLBACK   = int(os.getenv("CNT_FALLBACK", "40"))   # rows when no schools table
CNT_SEED       = os.getenv("CNT_SEED")                  # for deterministic data

# ---- Table names -------------------------------------------------------------
CONTACTS_TBL = "contacts"
SCHOOLS_TBL  = "schools"

# ---- Logging setup -----------------------------------------------------------
logging.getLogger("alembic.runtime.migration").setLevel(getattr(logging, LOG_LVL, logging.INFO))
_engine_logger = logging.getLogger("sqlalchemy.engine")
_engine_logger.setLevel(logging.INFO if LOG_SQL else getattr(logging, LOG_LVL, logging.INFO))


# ---- Helpers ----------------------------------------------------------------
def _outer_tx(conn):
    """Open a transaction only if one isn't already active (plays nice with env.py)."""
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


def _slugify(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return re.sub(r"-{2,}", "-", s).strip("-") or "school"


def _write_csv(bind) -> tuple[Path, int]:
    """
    (Re)generate contacts.csv.
    If a 'schools' table exists, generate CNT_PER_SCHOOL contacts per school using the school name
    to craft values (emails/phones/websites). Otherwise generate CNT_FALLBACK generic contacts.
    Returns (path, number_of_rows_written).
    """
    out = _default_output_path(CSV_NAME)
    out.parent.mkdir(parents=True, exist_ok=True)

    insp = sa.inspect(bind)
    have_contacts = insp.has_table(CONTACTS_TBL)
    if not have_contacts:
        log.info("[%s] Table %s missing; nothing to populate.", revision, CONTACTS_TBL)
        # still create header-only CSV for consistency
        with out.open("w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(["type", "value"])
        return out, 0

    rng = random.Random(CNT_SEED)
    contact_types = ["phone", "email", "website", "fax", "attendance_phone", "counseling_email"]

    def rand_phone() -> str:
        # (XYZ) ABC-DEF0
        area = rng.randint(200, 989)
        prefix = rng.randint(200, 889)
        line = rng.randint(1000, 9999)
        return f"({area}) {prefix}-{line:04d}"

    def rand_email(slug: str) -> str:
        user = rng.choice(["info", "contact", "office", "admin", "hello", "support"])
        tld = rng.choice(["k12.us", "school.org", "edu", "k12.example"])
        return f"{user}@{slug}.{tld}"

    def rand_site(slug: str) -> str:
        tld = rng.choice(["k12.us", "school.org", "edu"])
        return f"https://www.{slug}.{tld}"

    rows_written = 0
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["type", "value"])

        # Try to use schools for more realistic "school contacts"
        if insp.has_table(SCHOOLS_TBL):
            # try to fetch school names; fall back to ids if name column missing
            school_names: list[str] = []
            try:
                school_names = [r[0] for r in bind.execute(sa.text(f"SELECT name FROM {SCHOOLS_TBL} ORDER BY name")).fetchall()]
            except Exception:
                try:
                    school_names = [str(r[0]) for r in bind.execute(sa.text(f"SELECT id FROM {SCHOOLS_TBL} ORDER BY id")).fetchall()]
                except Exception:
                    school_names = []

            if not school_names:
                log.warning("[%s] %s present but no rows; writing fallback rows.", revision, SCHOOLS_TBL)

            targets = school_names if school_names else [f"School {i+1}" for i in range(max(1, CNT_FALLBACK // 3))]

            for name in targets:
                slug = _slugify(name)
                # ensure some diversity per school
                picks = rng.sample(contact_types, k=min(len(contact_types), max(2, CNT_PER_SCHOOL)))
                for k in range(CNT_PER_SCHOOL):
                    ctype = picks[k % len(picks)]
                    if "phone" in ctype:
                        value = rand_phone()
                    elif "email" in ctype:
                        value = rand_email(slug)
                    elif ctype == "website":
                        value = rand_site(slug)
                    else:
                        # generic fallback
                        value = rand_email(slug) if "email" in ctype else rand_phone()
                    w.writerow([ctype, value])
                    rows_written += 1
        else:
            # No schools table; write generic contacts
            for i in range(CNT_FALLBACK):
                ctype = rng.choice(contact_types)
                slug = f"school{i%17+1}"
                if "phone" in ctype:
                    value = rand_phone()
                elif "email" in ctype:
                    value = rand_email(slug)
                elif ctype == "website":
                    value = rand_site(slug)
                else:
                    value = rand_phone()
                w.writerow([ctype, value])
                rows_written += 1

    log.info("[%s] CSV generated with %d rows => %s", revision, rows_written, out)
    return out, rows_written


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
    Build INSERT for contacts. We avoid hardcoding created_at/updated_at so DB defaults apply.
    Use portable NOT-EXISTS guard on (type, value) to keep seeding idempotent.
    """
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns(CONTACTS_TBL)}

    ins_cols, vals = [], []
    def add(col: str, param: Optional[str] = None):
        if col in cols:
            ins_cols.append(col)
            vals.append(f":{param or col}")

    # we omit "id" (let server_default gen_random_uuid() handle it)
    add("type")
    add("value")

    cols_sql = ", ".join(ins_cols)
    select_list = ", ".join(vals)
    guard = (
        f" WHERE NOT EXISTS (SELECT 1 FROM {CONTACTS_TBL} t "
        f"WHERE t.type = :type AND t.value = :value)"
    )
    sql = sa.text(f"INSERT INTO {CONTACTS_TBL} ({cols_sql}) SELECT {select_list}{guard}")
    return sql, cols


# ---- Migration ---------------------------------------------------------------
def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if not insp.has_table(CONTACTS_TBL):
        log.info("[%s] Table %s missing; nothing to populate.", revision, CONTACTS_TBL)
        return

    csv_path, csv_rows = _write_csv(bind)
    reader, fobj = _open_csv(csv_path)

    insert_stmt, cols = _insert_sql(bind)
    log.debug("[%s] Insert SQL: %s", revision, getattr(insert_stmt, "text", str(insert_stmt)))

    total = inserted = skipped = 0
    try:
        with _outer_tx(bind):
            for idx, raw in enumerate(reader, start=1):
                total += 1
                if not raw:
                    continue
                row = { (k.strip() if isinstance(k, str) else k): (v.strip() if isinstance(v, str) else v)
                        for k, v in raw.items() }

                ctype = row.get("type") or None
                value = row.get("value") or None

                if not ctype or not value:
                    skipped += 1
                    if LOG_ROWS:
                        log.warning("[%s] row %d missing type/value — skipping: %r", revision, idx, row)
                    continue

                params = {"type": ctype, "value": value}
                params = {k: v for k, v in params.items() if k in cols}

                try:
                    bind.execute(insert_stmt, params)
                    inserted += 1
                    if LOG_ROWS:
                        log.info("[%s] row %d INSERT ok (type=%s, value=%s)", revision, idx, ctype, value)
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
        raise RuntimeError(f"[{revision}] No rows inserted; set CNT_LOG_ROWS=1 for per-row details.")


def downgrade() -> None:
    """
    Best-effort removal using the same CSV (if present): delete rows by (type, value).
    """
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if not insp.has_table(CONTACTS_TBL):
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
                ctype = (raw.get("type") or "").strip()
                value = (raw.get("value") or "").strip()
                if not ctype or not value:
                    continue
                try:
                    res = bind.execute(
                        sa.text(f"DELETE FROM {CONTACTS_TBL} WHERE type = :type AND value = :value"),
                        {"type": ctype, "value": value},
                    )
                    try:
                        deleted += res.rowcount or 0
                    except Exception:
                        pass
                except Exception:
                    if LOG_ROWS:
                        log.exception("[%s] downgrade delete failed for (%s, %s)", revision, ctype, value)
    finally:
        try:
            fobj.close()
        except Exception:
            pass

    log.info("[%s] downgrade removed ~%s rows from %s (based on CSV).",
             revision, deleted, CONTACTS_TBL)