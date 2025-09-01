# src/OSSS/db/migrations/versions/0081_populate_audit_logs.py
from __future__ import annotations

import os, csv, json, logging, uuid, random
from pathlib import Path
from contextlib import nullcontext
from typing import Optional

from alembic import op
import sqlalchemy as sa

# ---- Alembic identifiers ----
revision = "0082_populate_agenda_it_f"
down_revision = "0081_populate_audit_logs"  # update if needed
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

# ---- Config / env toggles ----------------------------------------------------
LOG_LVL        = os.getenv("AIF_LOG_LEVEL", "INFO").upper()
LOG_SQL        = os.getenv("AIF_LOG_SQL", "1") == "1"
LOG_ROWS       = os.getenv("AIF_LOG_ROWS", "1") == "1"
ABORT_IF_ZERO  = os.getenv("AIF_ABORT_IF_ZERO", "1") == "1"

CSV_ENV        = "AGENDA_ITEM_FILES_CSV_PATH"   # dir or full file path
CSV_NAME       = "agenda_item_files.csv"

# how many files to link per agenda_item (default 1)
AIF_LINKS_PER_ITEM = max(1, int(os.getenv("AIF_LINKS_PER_ITEM", "1")))
AIF_SEED           = os.getenv("AIF_SEED")  # set for deterministic pairing

# ---- Table names -------------------------------------------------------------
ITEMS_TBL   = "agenda_items"
FILES_TBL   = "files"
TARGET_TBL  = "agenda_item_files"
UQ_NAME     = "uq_agenda_item_files_pair"

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


def _ensure_unique_constraint(bind):
    """Ensure the (agenda_item_id, file_id) unique constraint exists and matches."""
    insp = sa.inspect(bind)
    if not insp.has_table(TARGET_TBL):
        return
    uqs = {u["name"]: u for u in insp.get_unique_constraints(TARGET_TBL)}
    desired_cols = ["agenda_item_id", "file_id"]
    if UQ_NAME in uqs and uqs[UQ_NAME]["column_names"] != desired_cols:
        op.drop_constraint(UQ_NAME, TARGET_TBL, type_="unique")
    if UQ_NAME not in uqs or (
        UQ_NAME in uqs and uqs[UQ_NAME]["column_names"] != desired_cols
    ):
        try:
            op.create_unique_constraint(UQ_NAME, TARGET_TBL, desired_cols)
        except Exception:
            pass


def _write_csv(bind) -> tuple[Path, int, int]:
    """
    Always (re)write agenda_item_files.csv using agenda_items.id and files.id.
    Strategy: for each agenda_item, attach up to AIF_LINKS_PER_ITEM distinct file(s).
    """
    out = _default_output_path(CSV_NAME)
    out.parent.mkdir(parents=True, exist_ok=True)

    insp = sa.inspect(bind)
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["agenda_item_id", "file_id", "caption"])

        if not (insp.has_table(ITEMS_TBL) and insp.has_table(FILES_TBL)):
            log.warning("[%s] Missing %s or %s; wrote header-only CSV: %s",
                        revision, ITEMS_TBL, FILES_TBL, out)
            return out, 0, 0

        item_rows = bind.execute(sa.text(f"SELECT id FROM {ITEMS_TBL} ORDER BY id")).fetchall()
        file_rows = bind.execute(sa.text(f"SELECT id FROM {FILES_TBL} ORDER BY id")).fetchall()
        item_ids = [str(r[0]) for r in item_rows]
        file_ids = [str(r[0]) for r in file_rows]

        if not item_ids or not file_ids:
            log.warning("[%s] No agenda_items or files; wrote header-only CSV: %s", revision, out)
            return out, len(item_ids), len(file_ids)

        rng = random.Random(AIF_SEED)
        for aid in item_ids:
            if AIF_LINKS_PER_ITEM >= len(file_ids):
                picks = file_ids[:]  # all of them
                rng.shuffle(picks)
            else:
                picks = rng.sample(file_ids, AIF_LINKS_PER_ITEM)
            for fid in picks:
                w.writerow([aid, fid, "Seeded agenda_item_file"])

    log.info("[%s] CSV generated with %d agenda_items × %d files (links/item=%d) => %s",
             revision, len(item_ids), len(file_ids), AIF_LINKS_PER_ITEM, out)
    return out, len(item_ids), len(file_ids)


def _open_csv(csv_path: Path):
    f = csv_path.open("r", encoding="utf-8", newline="")
    reader = csv.DictReader(f)
    log.info("[%s] CSV headers: %s", revision, reader.fieldnames)
    # peek first few rows for debug
    try:
        from itertools import islice
        preview = list(islice(reader, 5))
        log.info("[%s] First rows preview: %s", revision, preview)
        f.seek(0); next(reader)
    except Exception:
        pass
    return reader, f


def _insert_sql(bind):
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns(TARGET_TBL)}

    insert_cols: list[str] = []
    value_params: list[str] = []
    select_params: list[str] = []

    def add(col: str, param: Optional[str] = None):
        if col in cols:
            insert_cols.append(col)
            value_params.append(f":{param or col}")
            select_params.append(f":{param or col}")

    add("agenda_item_id")
    add("file_id")
    add("caption")

    col_list = ", ".join(insert_cols)

    if bind.dialect.name == "postgresql":
        # Prefer ON CONFLICT if the named unique exists
        uqs = {u["name"]: u for u in insp.get_unique_constraints(TARGET_TBL)}
        if UQ_NAME in uqs:
            stmt = sa.text(
                f"INSERT INTO {TARGET_TBL} ({col_list}) "
                f"VALUES ({', '.join(value_params)}) "
                f"ON CONFLICT ON CONSTRAINT {UQ_NAME} DO NOTHING"
            )
            return stmt, cols
        # fallback to NOT EXISTS SELECT pattern
    # Generic path (or PG without UQ name): INSERT ... SELECT ... WHERE NOT EXISTS
    where = (
        f" WHERE NOT EXISTS (SELECT 1 FROM {TARGET_TBL} t "
        f"WHERE t.agenda_item_id = :agenda_item_id AND t.file_id = :file_id)"
    )
    stmt = sa.text(
        f"INSERT INTO {TARGET_TBL} ({col_list}) "
        f"SELECT {', '.join(select_params)}{where}"
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

    csv_path, items_count, files_count = _write_csv(bind)
    reader, fobj = _open_csv(csv_path)

    insert_stmt, cols = _insert_sql(bind)

    total = inserted = skipped = 0
    try:
        with _outer_tx(bind):
            for idx, raw in enumerate(reader, start=1):
                total += 1
                if not raw:
                    continue
                row = {
                    (k.strip() if isinstance(k, str) else k):
                    (v.strip() if isinstance(v, str) else v)
                    for k, v in raw.items()
                }

                agenda_item_id = row.get("agenda_item_id") or None
                file_id        = row.get("file_id") or None
                caption        = row.get("caption") or None

                if not (agenda_item_id and file_id):
                    skipped += 1
                    if LOG_ROWS:
                        log.warning("[%s] row %d missing agenda_item_id/file_id — skipping: %r",
                                    revision, idx, row)
                    continue

                params = {
                    "agenda_item_id": agenda_item_id,
                    "file_id": file_id,
                    "caption": caption or "Seeded agenda_item_file",
                }
                params = {k: v for k, v in params.items() if k in cols}

                try:
                    bind.execute(insert_stmt, params)
                    inserted += 1
                    if LOG_ROWS:
                        log.info("[%s] row %d INSERT ok (agenda_item_id=%s file_id=%s)",
                                 revision, idx, agenda_item_id, file_id)
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

    # Only complain if both source tables had rows but nothing was inserted.
    if ABORT_IF_ZERO and items_count > 0 and files_count > 0 and inserted == 0:
        raise RuntimeError(f"[{revision}] No rows inserted; set AIF_LOG_ROWS=1 for per-row details.")


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not insp.has_table(TARGET_TBL):
        return
    try:
        res = bind.execute(sa.text(
            f"DELETE FROM {TARGET_TBL} WHERE caption = 'Seeded agenda_item_file'"
        ))
        try:
            log.info("[%s] downgrade removed %s seeded rows from %s", revision, res.rowcount, TARGET_TBL)
        except Exception:
            pass
    except Exception:
        log.exception("[%s] downgrade best-effort delete failed", revision)