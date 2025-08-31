"""Seed the files table from CSV (idempotent, verbose logging)."""

from __future__ import annotations

import os, csv, logging
from pathlib import Path
from datetime import datetime

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

# ---- Alembic identifiers ----
revision = "0052_populate_files"
down_revision = "0051_populate_documents"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

FILES_TBL = "files"
USERS_TBL = "users"
CSV_NAME  = "files.csv"

# ---------- helpers ----------
def _find_csv() -> Path | None:
    here = Path(__file__).resolve()
    candidates = [
        here.with_name(CSV_NAME),
        here.parent / "data" / CSV_NAME,
        here.parent.parent / "data" / CSV_NAME,
        Path(os.getenv("FILES_CSV_PATH", "")),
        Path.cwd() / CSV_NAME,
        Path("/mnt/data") / CSV_NAME,             # extra: common local path
    ]
    log.info("[%s] CSV search candidates:", revision)
    for p in candidates:
        if p and str(p):
            log.info("    - %s", p)
    for p in candidates:
        if p and str(p) and p.exists():
            log.info("[%s] using CSV: %s", revision, p)
            return p
    log.warning("[%s] no CSV found in candidates above.", revision)
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

def _pick_uuid_sql(bind) -> str:
    """Pick a UUID generator available in this DB."""
    try:
        has_gen = bind.execute(sa.text("SELECT 1 FROM pg_proc WHERE proname='gen_random_uuid'")).scalar()
        if has_gen:
            log.info("[%s] using gen_random_uuid()", revision)
            return "gen_random_uuid()"
    except Exception:
        pass
    try:
        has_uuid = bind.execute(sa.text("SELECT 1 FROM pg_proc WHERE proname='uuid_generate_v4'")).scalar()
        if has_uuid:
            log.info("[%s] using uuid_generate_v4()", revision)
            return "uuid_generate_v4()"
    except Exception:
        pass
    log.warning("[%s] no UUID helper found; INSERTs will fail if 'id' is required and not nullable.", revision)
    return "gen_random_uuid()"  # default; will error if missing

def _in_tx(bind) -> bool:
    """Best-effort check for active outer transaction on this bind."""
    try:
        val = bind.in_transaction()
        return bool(val() if callable(val) else val)
    except Exception:
        # Assume true when we can't tell (Alembic usually wraps in a tx)
        return True

# ---------- migration ----------
def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    # table exists?
    tables = set(insp.get_table_names(schema=None))
    if FILES_TBL not in tables:
        log.warning("[%s] '%s' table missing — abort.", revision, FILES_TBL)
        return

    csv_path = _find_csv()
    if not csv_path:
        log.warning("[%s] %s not found — abort.", revision, CSV_NAME)
        return

    cols = {c["name"] for c in insp.get_columns(FILES_TBL)}
    has_created_at = "created_at" in cols
    has_updated_at = "updated_at" in cols

    # optional user lookup by email
    sel_user_by_email = None
    if USERS_TBL in tables:
        user_cols = {c["name"] for c in insp.get_columns(USERS_TBL)}
        if "email" in user_cols:
            sel_user_by_email = sa.text(
                f"SELECT id FROM {USERS_TBL} WHERE lower(email)=lower(:email) LIMIT 1"
            )

    # natural key check for idempotence
    chk = sa.text(f"""
        SELECT 1 FROM {FILES_TBL}
        WHERE storage_key = :sk AND filename = :fn
        LIMIT 1
    """)

    uuid_sql = _pick_uuid_sql(bind)

    ins_cols = ["id","storage_key","filename","size","mime_type","created_by"]
    if has_created_at: ins_cols.append("created_at")
    if has_updated_at: ins_cols.append("updated_at")

    ins_vals = [uuid_sql, ":storage_key", ":filename", ":size", ":mime_type", ":created_by"]
    if has_created_at: ins_vals.append(":created_at")
    if has_updated_at: ins_vals.append(":updated_at")

    ins = sa.text(f"""
        INSERT INTO {FILES_TBL} ({", ".join(ins_cols)})
        VALUES ({", ".join(ins_vals)})
    """).bindparams(
        sa.bindparam("storage_key", type_=sa.String),
        sa.bindparam("filename", type_=sa.String),
        sa.bindparam("size"),
        sa.bindparam("mime_type", type_=sa.String),
        sa.bindparam("created_by"),
        sa.bindparam("created_at", type_=sa.DateTime(timezone=True)),
        sa.bindparam("updated_at", type_=sa.DateTime(timezone=True)),
    )

    inserted = skipped = failed = 0
    sample_first = []

    # Ensure we have an outer tx if Alembic/env.py isn't providing one
    outer_tx = None
    try:
        if not _in_tx(bind):
            log.info("[%s] no active transaction detected; starting outer transaction", revision)
            outer_tx = bind.begin()

        with csv_path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            log.info("[%s] CSV header: %s", revision, reader.fieldnames)

            for i, row in enumerate(reader, start=1):
                sk = (row.get("storage_key") or "").strip()
                fn = (row.get("filename") or "").strip()
                if not sk or not fn:
                    log.warning("[%s] row %d missing storage_key/filename; skipping", revision, i)
                    skipped += 1
                    continue

                # parse size
                raw_size = row.get("size")
                try:
                    size = int(raw_size) if raw_size not in (None, "",) else None
                except Exception:
                    size = None

                mime = (row.get("mime_type") or "").strip() or None

                created_by = None
                created_by_email = (row.get("created_by_email") or "").strip()
                if sel_user_by_email is not None and created_by_email:
                    try:
                        created_by = bind.execute(sel_user_by_email, {"email": created_by_email}).scalar()
                    except Exception:
                        created_by = None

                created_at = _parse_dt(row.get("created_at"))
                updated_at = _parse_dt(row.get("updated_at"))

                # Decide if we can use a savepoint
                supports_sp = bool(getattr(bind.dialect, "supports_savepoints", False))
                use_savepoint = supports_sp and _in_tx(bind)

                if use_savepoint:
                    try:
                        with bind.begin_nested():  # SAVEPOINT per row
                            exists = bind.execute(chk, {"sk": sk, "fn": fn}).scalar()
                            if exists:
                                skipped += 1
                            else:
                                bind.execute(ins, {
                                    "storage_key": sk,
                                    "filename": fn,
                                    "size": size,
                                    "mime_type": mime,
                                    "created_by": created_by,
                                    "created_at": created_at or datetime.utcnow(),
                                    "updated_at": updated_at or datetime.utcnow(),
                                })
                                inserted += 1
                                if len(sample_first) < 3:
                                    sample_first.append({"filename": fn, "storage_key": sk})
                    except Exception:
                        failed += 1
                        log.exception("[%s] row %d failed — continuing (filename=%r, storage_key=%r)", revision, i, fn, sk)
                else:
                    # No outer tx / no savepoints -> run row individually.
                    # If we created an outer tx, rollback and reopen it on failure so later rows still work.
                    try:
                        exists = bind.execute(chk, {"sk": sk, "fn": fn}).scalar()
                        if exists:
                            skipped += 1
                        else:
                            bind.execute(ins, {
                                "storage_key": sk,
                                "filename": fn,
                                "size": size,
                                "mime_type": mime,
                                "created_by": created_by,
                                "created_at": created_at or datetime.utcnow(),
                                "updated_at": updated_at or datetime.utcnow(),
                            })
                            inserted += 1
                            if len(sample_first) < 3:
                                sample_first.append({"filename": fn, "storage_key": sk})
                    except Exception:
                        failed += 1
                        log.exception("[%s] row %d failed — continuing (filename=%r, storage_key=%r)", revision, i, fn, sk)
                        if outer_tx is not None:
                            try:
                                outer_tx.rollback()
                            except Exception:
                                pass
                            try:
                                outer_tx = bind.begin()
                            except Exception:
                                outer_tx = None

        log.info("[%s] inserted=%d, skipped=%d, failed=%d", revision, inserted, skipped, failed)
        if sample_first:
            log.info("[%s] sample inserted rows: %s", revision, sample_first)
    finally:
        if outer_tx is not None:
            try:
                outer_tx.commit()
            except Exception:
                # Alembic may be managing the commit already
                pass

def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if FILES_TBL not in insp.get_table_names(schema=None):
        return
    csv_path = _find_csv()
    if not csv_path:
        return

    pairs = []
    with csv_path.open("r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            sk = (row.get("storage_key") or "").strip()
            fn = (row.get("filename") or "").strip()
            if sk and fn:
                pairs.append((sk, fn))
    if not pairs:
        return

    del_stmt = sa.text(f"""
        DELETE FROM {FILES_TBL}
        WHERE (storage_key, filename) IN (
            SELECT unnest(:sks), unnest(:fns)
        )
    """).bindparams(
        sa.bindparam("sks", value=[p[0] for p in pairs], type_=pg.ARRAY(sa.String)),
        sa.bindparam("fns", value=[p[1] for p in pairs], type_=pg.ARRAY(sa.String)),
    )
    bind.execute(del_stmt)
