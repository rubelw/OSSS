from __future__ import annotations

import csv
import logging
import os
import random
import uuid
from datetime import date, timedelta, datetime, timezone
from typing import List, Dict, Tuple

from alembic import op
import sqlalchemy as sa

# ---- Alembic identifiers ----
revision = "0101_seed_mtg_doc"
down_revision = "0100_seed_ag_itm"  # update if needed
branch_labels = None
depends_on = None

# ---- Logging ---------------------------------------------------------------
log = logging.getLogger("alembic.runtime.migration")

# --- Config / knobs ---
CSV_FILENAME = "meeting_documents.csv"
DEFAULT_ROW_COUNT = int(os.getenv("MEETING_DOC_ROWS", "300"))
SEED = os.getenv("MEETING_DOC_SEED")  # e.g. "42" for reproducibility
ABORT_IF_ZERO = os.getenv("ABORT_IF_ZERO", "0") == "1"

LABELS = [
    "Agenda",
    "Minutes",
    "Slide Deck",
    "Staff Report",
    "Attachment A",
    "Attachment B",
    "Public Notice",
    "Background",
    "Handout",
    "Summary",
]

def _csv_path() -> str:
    """Write CSV next to this migration file."""
    return os.path.join(os.path.dirname(__file__), CSV_FILENAME)

def _fetch_all_scalar(conn, sql: str) -> List[str]:
    return [r[0] for r in conn.execute(sa.text(sql)).fetchall()]

def _fetch_reference_data(conn):
    meeting_ids = _fetch_all_scalar(conn, "SELECT id FROM meetings")
    document_ids = _fetch_all_scalar(conn, "SELECT id FROM documents")
    return meeting_ids, document_ids

def _generate_rows(
    meeting_ids: List[str],
    document_ids: List[str],
    max_rows: int,
) -> List[Dict[str, object]]:
    """
    Generate random meeting-document links.
    We ensure (meeting_id, document_id, label) tuples don't duplicate within this batch.
    """
    if SEED is not None:
        try:
            random.seed(int(SEED))
        except ValueError:
            random.seed(SEED)

    if not meeting_ids:
        msg = "[meeting_documents] no meetings found; skipping seed."
        if ABORT_IF_ZERO:
            raise RuntimeError(msg)
        log.info(msg)
        return []
    if not document_ids:
        # If you prefer to allow NULL document_id rows, you could relax this.
        # The requirement says document_id should be populated from documents, so enforce it.
        msg = "[meeting_documents] no documents found; skipping seed."
        if ABORT_IF_ZERO:
            raise RuntimeError(msg)
        log.info(msg)
        return []

    rows: List[Dict[str, object]] = []
    used = set()

    target = max_rows
    now = datetime.now(timezone.utc)

    while len(rows) < target:
        mid = random.choice(meeting_ids)
        did = random.choice(document_ids)
        label = random.choice(LABELS)

        key = (mid, did, label)
        if key in used:
            continue
        used.add(key)

        # Provide a plausible file_uri that references the document id.
        # (Adjust to your storage/path scheme if desired.)
        file_uri = f"/documents/{did}"

        rows.append(
            {
                "id": str(uuid.uuid4()),
                "meeting_id": mid,
                "document_id": did,
                "file_uri": file_uri,
                "label": label,
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
            }
        )

    return rows

def _write_csv(csv_path: str, rows: List[Dict[str, object]]) -> None:
    fieldnames = [
        "id",
        "meeting_id",
        "document_id",
        "file_uri",
        "label",
        "created_at",
        "updated_at",
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)

def _read_csv(csv_path: str) -> List[Dict[str, object]]:
    with open(csv_path, "r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))

def upgrade():
    conn = op.get_bind()

    log.info("[0101] meeting_documents: fetching reference data…")
    meeting_ids, document_ids = _fetch_reference_data(conn)
    log.info("[0101] meeting_documents: %d meetings, %d documents found", len(meeting_ids), len(document_ids))

    log.info("[0101] meeting_documents: generating %d rows…", DEFAULT_ROW_COUNT)
    rows = _generate_rows(meeting_ids, document_ids, DEFAULT_ROW_COUNT)
    if not rows:
        log.info("[0101] meeting_documents: nothing to insert; exiting migration.")
        return

    csv_path = _csv_path()
    log.info("[0101] meeting_documents: writing CSV at %s (%d rows)…", csv_path, len(rows))
    _write_csv(csv_path, rows)

    # Be idempotent within this migration: clear table, then insert.
    log.info("[0101] meeting_documents: clearing table…")
    conn.execute(sa.text("DELETE FROM meeting_documents"))

    data = _read_csv(csv_path)

    table = sa.table(
        "meeting_documents",
        sa.column("id", sa.String),
        sa.column("meeting_id", sa.String),
        sa.column("document_id", sa.String),
        sa.column("file_uri", sa.Text),
        sa.column("label", sa.Text),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )

    # Convert types
    to_insert = []
    for r in data:
        to_insert.append(
            {
                "id": r["id"],
                "meeting_id": r["meeting_id"],
                "document_id": r["document_id"] or None,
                "file_uri": (r.get("file_uri") or None),
                "label": (r.get("label") or None),
                "created_at": datetime.fromisoformat(r["created_at"]),
                "updated_at": datetime.fromisoformat(r["updated_at"]),
            }
        )

    log.info("[0101] meeting_documents: inserting %d rows…", len(to_insert))
    CHUNK = 1000
    for i in range(0, len(to_insert), CHUNK):
        op.bulk_insert(table, to_insert[i : i + CHUNK])
    log.info("[0101] meeting_documents: done.")

def downgrade():
    conn = op.get_bind()
    log.info("[0101] meeting_documents: deleting all rows (downgrade)…")
    conn.execute(sa.text("DELETE FROM meeting_documents"))
