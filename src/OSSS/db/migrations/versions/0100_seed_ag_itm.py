# src/OSSS/db/migrations/versions/0100_seed_ag_itm.py
from __future__ import annotations

import csv
import logging
import os
import random
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql.sqltypes import (
    DateTime as _SQLADateTime,
    Boolean as _SQLABoolean,
    Integer as _SQLAInteger,
)

# ---- Alembic identifiers ----
revision = "0100_seed_ag_itm"
down_revision = "0099_seed_meetings"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

CSV_FILENAME = "agenda_items.csv"
DEFAULT_ITEMS_PER_MEETING = int(os.getenv("AGENDA_ITEMS_PER_MEETING", "6"))
SEED = os.getenv("AGENDA_ITEM_SEED")  # e.g. "42")


# ----------------------------- helpers --------------------------------------
def _resolve_table_name(conn, candidates: tuple[str, ...]) -> Optional[str]:
    insp = sa.inspect(conn)
    for name in candidates:
        try:
            if insp.has_table(name):
                return name
        except Exception:
            if conn.dialect.name == "postgresql":
                ok = conn.execute(sa.text("SELECT to_regclass(:n) IS NOT NULL"), {"n": name}).scalar()
                if ok:
                    return name
    return None


def _table_exists(conn, name: str) -> bool:
    try:
        conn.execute(sa.text(f'SELECT 1 FROM "{name}" LIMIT 1'))
        return True
    except Exception:
        return False


def _csv_path() -> str:
    return os.path.join(os.path.dirname(__file__), CSV_FILENAME)


def _fetch_ids(conn, table: str) -> List[str]:
    return [r[0] for r in conn.execute(sa.text(f'SELECT id FROM "{table}"')).fetchall()]


def _fetch_meeting_ids(conn) -> List[str]:
    return _fetch_ids(conn, "meetings")


def _pick_optional_id(pool: List[str], p: float) -> Optional[str]:
    if pool and random.random() < p:
        return random.choice(pool)
    return None


def _generate_rows(
    meeting_ids: List[str],
    policy_ids: List[str],
    objective_ids: List[str],
    items_per_meeting: int,
) -> List[Dict[str, object]]:
    """Generate rows that match the NEW AgendaItem schema."""
    if SEED is not None:
        try:
            random.seed(int(SEED))
        except ValueError:
            random.seed(SEED)

    titles = [
        "Opening Remarks",
        "New Business",
        "Old Business",
        "Program Update",
        "Assessment Alignment",
        "Instructional Materials",
        "Community Input",
        "Action Items",
        "Policy Discussion",
    ]
    descriptions = [
        "Discussion led by chair.",
        "Review supporting documents.",
        "Public comment period included.",
        None,
    ]

    now = datetime.now(timezone.utc).isoformat()
    rows: List[Dict[str, object]] = []

    for m_id in meeting_ids:
        # mild variety per meeting
        n = max(1, items_per_meeting + random.choice([-1, 0, 1]))
        parent_for_children: Optional[str] = None

        for pos in range(1, n + 1):
            # a few items become children of the first (or prior) root
            if pos == 1 or parent_for_children is None:
                parent_id = None
            else:
                parent_id = parent_for_children if random.random() < 0.30 else None

            if pos == 1:
                parent_for_children = str(uuid.uuid4())
                this_id = parent_for_children
            else:
                this_id = str(uuid.uuid4())

            rows.append(
                {
                    "id": this_id,
                    "meeting_id": m_id,
                    "parent_id": parent_id,
                    "position": pos,  # DB allows 0; 1..n also valid (>=0)
                    "title": f"{random.choice(titles)} #{random.randint(1,6)}",
                    "description": random.choice(descriptions),
                    "linked_policy_id": _pick_optional_id(policy_ids, 0.30),
                    "linked_objective_id": _pick_optional_id(objective_ids, 0.40),
                    # NEW schema field name:
                    "time_allocated": random.choice([None, 5, 10, 15, 20, 30, 45, 60]),
                    "created_at": now,
                    "updated_at": now,
                }
            )

    return rows


def _write_csv(path: str, rows: List[Dict[str, object]]) -> None:
    if not rows:
        with open(path, "w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=["id"]).writeheader()
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for r in rows:
            w.writerow(r)


def _read_csv(path: str) -> List[Dict[str, object]]:
    with open(path, "r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _to_dt(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    return datetime.fromisoformat(s.replace("Z", ""))


def _to_int(v: object) -> Optional[int]:
    if v in (None, ""):
        return None
    try:
        return int(v)
    except Exception:
        return None


# ----------------------------- migration -------------------------------------
def upgrade():
    conn = op.get_bind()
    insp = sa.inspect(conn)

    items_tbl = _resolve_table_name(conn, ("agenda_items",))
    if not items_tbl:
        log.warning("[agenda_items] table not found; skipping.")
        return

    meetings_tbl = _resolve_table_name(conn, ("meetings",))
    if not meetings_tbl:
        log.warning("[agenda_items] meetings table not found; skipping.")
        return

    meeting_ids = _fetch_meeting_ids(conn)
    if not meeting_ids:
        log.info("[agenda_items] no meetings present; nothing to seed.")
        return

    # Optional link targets — use if the tables exist
    policy_tbl = _resolve_table_name(conn, ("policies", "cic_policies"))
    objective_tbl = _resolve_table_name(conn, ("objectives", "strategic_objectives", "goals"))

    policy_ids = _fetch_ids(conn, policy_tbl) if policy_tbl else []
    objective_ids = _fetch_ids(conn, objective_tbl) if objective_tbl else []

    # Generate + write CSV
    rows = _generate_rows(meeting_ids, policy_ids, objective_ids, DEFAULT_ITEMS_PER_MEETING)
    csv_path = _csv_path()
    _write_csv(csv_path, rows)
    log.info("[agenda_items] wrote CSV: %s (rows=%d)", csv_path, len(rows))
    if not rows:
        return

    # Reflect target columns and types
    cols_info = {c["name"]: c for c in insp.get_columns(items_tbl)}
    present = set(cols_info.keys())

    # Ensure we use the NEW minutes field name; if the table is older, quietly drop it
    minutes_col = "time_allocated" if "time_allocated" in present else None

    # Omit timestamp columns that aren't real timestamps (avoid TSVECTOR mismatch, etc.)
    def _is_dt(col: str) -> bool:
        return isinstance(cols_info[col]["type"], _SQLADateTime)

    for tscol in ("created_at", "updated_at"):
        if tscol in present and not _is_dt(tscol):
            log.warning("[agenda_items] '%s' exists but type=%s; omitting.",
                        tscol, cols_info[tscol]["type"])
            present.remove(tscol)

    # Build SA table with only the columns we'll insert
    def _col_type(col: str):
        t = cols_info[col]["type"]
        if isinstance(t, _SQLADateTime):
            return sa.DateTime(timezone=getattr(t, "timezone", False))
        if isinstance(t, _SQLABoolean):
            return sa.Boolean()
        if isinstance(t, _SQLAInteger):
            return sa.Integer()
        return sa.Text()

    desired_order = [
        "id",
        "meeting_id",
        "parent_id",
        "position",
        "title",
        "description",
        "linked_policy_id",
        "linked_objective_id",
        "time_allocated",  # new field
        "created_at",
        "updated_at",
    ]

    # keep only columns that actually exist
    ordered_columns = [c for c in desired_order if c in present and (c != "time_allocated" or minutes_col)]
    table = sa.table(items_tbl, *(sa.column(c, _col_type(c)) for c in ordered_columns))

    # Normalize CSV rows to present columns
    data = _read_csv(csv_path)
    to_insert: List[Dict[str, object]] = []
    for r in data:
        rec: Dict[str, object] = {}
        for c in ordered_columns:
            if c in {"created_at", "updated_at"}:
                rec[c] = _to_dt(r.get(c))
            elif c == "time_allocated":
                rec[c] = _to_int(r.get("time_allocated"))
            elif c == "position":
                rec[c] = _to_int(r.get("position")) or 0
            else:
                rec[c] = r.get(c) or None
        to_insert.append(rec)

    # Clear existing rows (idempotent reseed)
    conn.execute(sa.text(f'DELETE FROM "{items_tbl}"'))
    log.info("[agenda_items] table '%s' cleared", items_tbl)

    # Insert in chunks
    CHUNK = 1000
    total = 0
    for i in range(0, len(to_insert), CHUNK):
        batch = to_insert[i : i + CHUNK]
        if not batch:
            continue
        op.bulk_insert(table, batch)
        total += len(batch)
        log.info("[agenda_items] inserted batch %d..%d (batch=%d)", i + 1, i + len(batch), len(batch))

    log.info("[agenda_items] complete; inserted=%d", total)


def downgrade():
    conn = op.get_bind()
    items_tbl = _resolve_table_name(conn, ("agenda_items",))
    if not items_tbl:
        log.warning("[agenda_items] downgrade: table not found; nothing to delete.")
        return
    conn.execute(sa.text(f'DELETE FROM "{items_tbl}"'))
    log.info("[agenda_items] downgraded; table '%s' cleared (CSV left on disk)", items_tbl)
