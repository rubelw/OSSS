"""Populate document_versions from CSV (tolerant headers; creates missing docs/files; idempotent)."""

from __future__ import annotations

import os, csv, logging, re
from pathlib import Path
from datetime import datetime
from contextlib import nullcontext

from alembic import op
import sqlalchemy as sa

# ---- Alembic identifiers ----
revision = "0053_populate_doc_vers"
down_revision = "0052_populate_files"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

# optional runtime controls
try:
    if os.getenv("DV_SQL_ECHO") == "1":
        bind.engine.echo = True
except Exception:
    pass
lvl = os.getenv("DV_LOG_LEVEL", "INFO").upper()
logging.getLogger("alembic.runtime.migration").setLevel(getattr(logging, lvl, logging.INFO))
logging.getLogger("sqlalchemy.engine").setLevel(getattr(logging, lvl, logging.INFO))

DOCS_TBL   = "documents"
FILES_TBL  = "files"
DV_TBL     = "document_versions"
USERS_TBL  = "users"
CSV_NAME   = "document_versions.csv"

# ---------- logging helpers ----------
def _setup_logging():
    """Make the migration chatty when DV_LOG_LEVEL=DEBUG and/or DV_SQL_ECHO=1 are set."""
    level = os.getenv("DV_LOG_LEVEL", "INFO").upper()
    lvl = getattr(logging, level, logging.INFO)
    # ensure our logger has a handler so messages don't get swallowed
    if not log.handlers:
        h = logging.StreamHandler()
        h.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
        log.addHandler(h)
    log.setLevel(lvl)

    # optional: echo SQL emitted by SQLAlchemy engine
    if os.getenv("DV_SQL_ECHO"):
        sa_log = logging.getLogger("sqlalchemy.engine")
        if not sa_log.handlers:
            h2 = logging.StreamHandler()
            h2.setFormatter(logging.Formatter("[%(levelname)s sqlalchemy] %(message)s"))
            sa_log.addHandler(h2)
        sa_log.setLevel(logging.INFO)

# ---------- CSV / util ----------
def _find_csv() -> Path | None:
    here = Path(__file__).resolve()
    candidates = [
        here.with_name(CSV_NAME),
        here.parent / "data" / CSV_NAME,
        here.parent.parent / "data" / CSV_NAME,
        Path(os.getenv("DOCUMENT_VERSIONS_CSV_PATH", "")),
        Path.cwd() / CSV_NAME,
        Path("/mnt/data") / CSV_NAME,
    ]
    log.info("[%s] CSV search candidates:", revision)
    for p in candidates:
        if p and str(p):
            log.info("    - %s", p)
    for p in candidates:
        if p and str(p) and p.exists():
            log.info("[%s] using CSV: %s", revision, p)
            return p
    log.error("[%s] CSV NOT FOUND among candidates above", revision)
    return None

def _parse_dt(s: str | None):
    if not s:
        return None
    v = s.strip()
    if not v:
        return None
    try:
        if v.endswith("Z"):
            v = v[:-1]
        return datetime.fromisoformat(v)
    except Exception:
        return None

def _infer_mime(filename: str) -> str | None:
    fn = filename.lower()
    if fn.endswith(".pdf"):  return "application/pdf"
    if fn.endswith(".doc"):  return "application/msword"
    if fn.endswith(".docx"): return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    if fn.endswith(".xls"):  return "application/vnd.ms-excel"
    if fn.endswith(".xlsx"): return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    if fn.endswith(".ppt"):  return "application/vnd.ms-powerpoint"
    if fn.endswith(".pptx"): return "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    if fn.endswith(".txt"):  return "text/plain"
    if fn.endswith(".md"):   return "text/markdown"
    if fn.endswith(".jpg") or fn.endswith(".jpeg"): return "image/jpeg"
    if fn.endswith(".png"):  return "image/png"
    return None

def _uuid_sql(bind) -> str:
    for name in ("gen_random_uuid", "uuid_generate_v4"):
        try:
            if bind.execute(sa.text("SELECT 1 FROM pg_proc WHERE proname=:n"), {"n": name}).scalar():
                log.debug("[%s] using %s()", revision, name)
                return f"{name}()"
        except Exception:
            pass
    log.warning("[%s] no UUID helper detected; defaulting to gen_random_uuid()", revision)
    return "gen_random_uuid()"

_norm_ws_re = re.compile(r"\s+")
def _norm_key(k: str) -> str:
    k = k.replace("\ufeff", "").strip().lower()
    k = _norm_ws_re.sub("_", k)
    return k

def _normalize_row(row: dict) -> dict:
    return {_norm_key(k): v for k, v in row.items()}

def _pick(row: dict, candidates: list[str]) -> str | None:
    for c in candidates:
        if c in row and row[c] not in (None, "", "NULL", "null"):
            return str(row[c]).strip()
    return None

TITLE_KEYS = ["document_title","title","document","doc_title","documentname","document_name"]
FILENAME_KEYS = ["filename","file","file_name","name"]
FILE_BASENAME_KEYS = ["file_basename","basename"]
STORAGE_KEYS = ["storage_key","path","storage","key"]
VERSION_KEYS = ["version_no","version","ver","v","version_number"]
CHECKSUM_KEYS = ["checksum","sha1","sha256","md5"]
CREATED_BY_EMAIL_KEYS = ["created_by_email","creator_email","author_email"]
CREATED_AT_KEYS = ["created_at","createdon","created_on"]
PUBLISHED_AT_KEYS = ["published_at","publishedon","published_on"]

def _intify_version(s: str | None) -> int:
    if not s:
        return 1
    m = re.search(r"\d+", s.strip())
    return int(m.group(0)) if m else 1

def _ensure_outer_tx(conn):
    """
    Ensure there is an outer transaction. If Alembic already opened one,
    return a no-op context; otherwise start a top-level transaction.
    """
    try:
        if hasattr(conn, "get_transaction"):
            if conn.get_transaction() is not None:
                return nullcontext()
        if hasattr(conn, "in_transaction") and conn.in_transaction():
            return nullcontext()
    except Exception:
        return nullcontext()
    return conn.begin()

def _per_row_tx(conn):
    """
    Use SAVEPOINT for each row if possible under the outer Alembic transaction.
    If SAVEPOINT isn't available, no-op instead of starting another .begin().
    """
    try:
        return conn.begin_nested()
    except Exception:
        return nullcontext()

def _open_csv(csv_path: Path):
    raw = csv_path.read_text(encoding="utf-8", errors="ignore")
    sample = raw.splitlines(True)[:10]
    try:
        dialect = csv.Sniffer().sniff("".join(sample), delimiters=",\t;|")
        log.debug("[%s] CSV dialect detected: delimiter=%r", revision, dialect.delimiter)
    except Exception:
        dialect = csv.get_dialect("excel")
        log.debug("[%s] CSV dialect defaulted to 'excel' (,)", revision)
    f = csv_path.open("r", encoding="utf-8", newline="")
    return csv.DictReader(f, dialect=dialect), f

# ---------- migration ----------
def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    # ---- turn up SQL logging (shows SQL + params) ----
    logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)
    logging.getLogger("sqlalchemy.pool").setLevel(logging.INFO)

    # ---- basic table presence check ----
    have = set(insp.get_table_names(schema=None))
    for t in (DOCS_TBL, FILES_TBL, DV_TBL):
        if t not in have:
            log.error("[%s] table %r missing — abort.", revision, t)
            return

    # ---- locate CSV ----
    csv_path = _find_csv()
    if not csv_path:
        raise RuntimeError(f"[{revision}] document_versions.csv not found")

    uuid_sql = _uuid_sql(bind)

    # ---- prepared statements ----
    sel_doc_by_title = sa.text(f"SELECT id FROM {DOCS_TBL} WHERE lower(title)=lower(:title) LIMIT 1")
    sel_file_by_name = sa.text(f"SELECT id FROM {FILES_TBL} WHERE lower(filename)=lower(:fn) LIMIT 1")

    sel_user_by_email = None
    if USERS_TBL in have and "email" in {c["name"] for c in insp.get_columns(USERS_TBL)}:
        sel_user_by_email = sa.text(
            f"SELECT id FROM {USERS_TBL} WHERE lower(email)=lower(:email) LIMIT 1"
        )

    ins_doc = sa.text(
        f"INSERT INTO {DOCS_TBL} (id, title, is_public) "
        f"VALUES ({uuid_sql}, :title, FALSE) RETURNING id"
    )
    ins_file = sa.text(
        f"INSERT INTO {FILES_TBL} (id, storage_key, filename, size, mime_type, created_at, updated_at) "
        f"VALUES ({uuid_sql}, :sk, :fn, :size, :mime, now(), now()) RETURNING id"
    )
    sel_dv_exists = sa.text(
        f"SELECT 1 FROM {DV_TBL} WHERE document_id=:doc_id AND version_no=:ver LIMIT 1"
    )
    ins_dv = sa.text(
        f"INSERT INTO {DV_TBL} "
        f"(id, document_id, version_no, file_id, checksum, created_by, created_at, published_at) "
        f"VALUES ({uuid_sql}, :doc_id, :ver, :file_id, :checksum, :created_by, :created_at, :published_at)"
    )

    # ---- counters for diagnostics ----
    total_rows = 0
    inserted = 0
    skipped = 0
    existed = 0
    missing = 0
    errors = 0
    created_docs = 0
    created_files = 0

    # ---- open CSV (auto-detect dialect) ----
    reader, fobj = _open_csv(csv_path)
    try:
        log.info("[%s] CSV header (raw): %s", revision, reader.fieldnames)

        # preview first 3 rows (normalized)
        preview = []
        for _ in range(3):
            try:
                _raw = next(reader)
            except StopIteration:
                break
            preview.append(_normalize_row(_raw))
        if preview:
            log.info("[%s] preview (first 3 normalized rows): %s", revision, preview)

        # rewind
        fobj.seek(0)
        reader, _ = _open_csv(csv_path)

        # ---- one outer txn; per-row savepoints inside ----
        with _ensure_outer_tx(bind):
            for idx, raw in enumerate(reader, start=1):
                total_rows += 1
                row = _normalize_row(raw)

                # make visible even if we fail early
                title = None
                filename = None
                ver = None
                checksum = None
                created_by_email = None
                created_at = None
                published_at = None

                # parse row
                title = _pick(row, TITLE_KEYS)
                filename = _pick(row, FILENAME_KEYS)
                if not filename:
                    fb = _pick(row, ["file_basename", "basename"])
                    if fb:
                        filename = Path(fb).name.strip()
                if not filename:
                    sk = _pick(row, STORAGE_KEYS)
                    if sk:
                        filename = Path(sk).name

                ver = _intify_version(_pick(row, VERSION_KEYS))
                checksum = _pick(row, CHECKSUM_KEYS)
                created_by_email = _pick(row, CREATED_BY_EMAIL_KEYS)
                created_at = _parse_dt(_pick(row, CREATED_AT_KEYS)) or datetime.utcnow()
                published_at = _parse_dt(_pick(row, PUBLISHED_AT_KEYS))

                if not title or not filename:
                    missing += 1
                    skipped += 1
                    if idx <= 10:
                        log.warning("[%s] row %d: missing title/filename; keys=%s row=%s",
                                    revision, idx, list(row.keys()), row)
                    continue

                log.info("[%s] row %d: title=%r filename=%r version=%s", revision, idx, title, filename, ver)

                try:
                    with _per_row_tx(bind):
                        # ---- document lookup / create ----
                        doc_id = bind.execute(sel_doc_by_title, {"title": title}).scalar()
                        log.info("[%s] row %d: doc lookup -> %s", revision, idx, doc_id)
                        if not doc_id:
                            res = bind.execute(ins_doc, {"title": title})
                            doc_id = res.scalar()
                            created_docs += 1
                            log.info("[%s] row %d: created document %r -> %s", revision, idx, title, doc_id)

                        # ---- file lookup / create ----
                        file_id = bind.execute(sel_file_by_name, {"fn": filename}).scalar()
                        log.info("[%s] row %d: file lookup -> %s", revision, idx, file_id)
                        if not file_id:
                            mime = _infer_mime(filename)
                            sk = f"uploads/seed/{filename}"
                            log.info("[%s] row %d: creating file sk=%r fn=%r mime=%r", revision, idx, sk, filename, mime)
                            res = bind.execute(ins_file, {"sk": sk, "fn": filename, "size": None, "mime": mime})
                            file_id = res.scalar()
                            created_files += 1
                            log.info("[%s] row %d: created file %r -> %s", revision, idx, filename, file_id)

                        # ---- user (optional) ----
                        created_by = None
                        if (sel_user_by_email is not None) and created_by_email:
                            created_by = bind.execute(sel_user_by_email, {"email": created_by_email}).scalar()
                            log.info("[%s] row %d: user lookup %r -> %s", revision, idx, created_by_email, created_by)

                        # ---- dv exists? ----
                        dv_exists = bind.execute(sel_dv_exists, {"doc_id": doc_id, "ver": ver}).scalar()
                        log.info("[%s] row %d: dv_exists(doc_id=%s, ver=%s) -> %r",
                                 revision, idx, doc_id, ver, dv_exists)

                        if dv_exists:
                            existed += 1
                            skipped += 1
                            continue

                        # ---- insert dv ----
                        params = {
                            "doc_id": doc_id,
                            "ver": ver,
                            "file_id": file_id,
                            "checksum": checksum,
                            "created_by": created_by,
                            "created_at": created_at,
                            "published_at": published_at,
                        }
                        log.info("[%s] row %d: inserting DV with params=%s", revision, idx, params)
                        res = bind.execute(ins_dv, params)
                        inserted += 1
                        log.info("[%s] row %d: DV inserted; rowcount=%s", revision, idx, res.rowcount)

                except Exception as e:
                    errors += 1
                    skipped += 1
                    log.exception("[%s] row %d: FAILED (title=%r, file=%r, v=%s) — continuing",
                                  revision, idx, title, filename, ver)

    finally:
        fobj.close()

    log.info("[%s] SUMMARY: rows_in_csv=%d inserted=%d skipped=%d (missing=%d existed=%d errors=%d) "
             "created_docs=%d created_files=%d",
             revision, total_rows, inserted, skipped, missing, existed, errors, created_docs, created_files)

    # only fail if literally nothing changed and nothing was even created (helps surface header/csv issues)
    if total_rows > 0 and inserted == 0 and created_docs == 0 and created_files == 0 and errors == 0:
        raise RuntimeError(f"[{revision}] Processed {total_rows} rows but inserted 0; check header/field names.")

def downgrade() -> None:
    _setup_logging()
    bind = op.get_bind()
    if DV_TBL not in sa.inspect(bind).get_table_names(schema=None):
        return
    csv_path = _find_csv()
    if not csv_path:
        return
    sel_doc_by_title = sa.text(f"SELECT id FROM {DOCS_TBL} WHERE lower(title)=lower(:title) LIMIT 1")

    def _normalize_row(row: dict) -> dict:
        return {_norm_key(k): v for k, v in row.items()}

    reader, fobj = _open_csv(csv_path)
    try:
        pairs = []
        for raw in reader:
            row = _normalize_row(raw)
            title = _pick(row, TITLE_KEYS)
            ver = _intify_version(_pick(row, VERSION_KEYS))
            if not title:
                continue
            doc_id = bind.execute(sel_doc_by_title, {"title": title}).scalar()
            if doc_id:
                pairs.append((doc_id, ver))
        if not pairs:
            return
        params, values = {}, []
        for i, (d, v) in enumerate(pairs):
            params[f"d{i}"] = d; params[f"v{i}"] = v
            values.append(f"(:d{i}, :v{i})")
        del_stmt = sa.text(f"DELETE FROM {DV_TBL} WHERE (document_id, version_no) IN (VALUES {', '.join(values)})")
        bind.execute(del_stmt, params)
    finally:
        fobj.close()
