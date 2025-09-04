# src/OSSS/db/migrations/versions/0099_seed_meetings.py
from __future__ import annotations

import csv
import logging
import os
import random
import uuid
from datetime import timedelta, datetime, timezone
from typing import List, Dict, Optional, Tuple

from alembic import op
import sqlalchemy as sa

# ---- Alembic identifiers ----
revision = "0099_seed_meetings"
down_revision = "0098_seed_comm"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

CSV_FILENAME = "meetings.csv"
DEFAULT_ROW_COUNT = int(os.getenv("MEETING_ROWS", "40"))
SEED = os.getenv("MEETING_SEED")  # e.g. "42"


# ----------------------------- helpers --------------------------------------
def _resolve_table_name(conn, candidates: tuple[str, ...]) -> Optional[str]:
    insp = sa.inspect(conn)
    for name in candidates:
        try:
            if insp.has_table(name):
                return name
        except Exception:
            if conn.dialect.name == "postgresql":
                ok = conn.execute(
                    sa.text("SELECT to_regclass(:n) IS NOT NULL"), {"n": name}
                ).scalar()
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


def _fetch_committees(conn, committees_tbl: str) -> List[Tuple[str, Optional[str]]]:
    """
    Return list of (committee_id, org_id) for seeding meetings.
    org_id is derived as:
       COALESCE(committees.organization_id, schools.organization_id)
    If schools table is absent, fall back to committees.organization_id only.
    """
    insp = sa.inspect(conn)
    cols = {c["name"] for c in insp.get_columns(committees_tbl)}

    org_col = "organization_id" if "organization_id" in cols else (
        "org_id" if "org_id" in cols else None
    )
    if not org_col:
        raise RuntimeError(f"[meetings] '{committees_tbl}' lacks organization_id column.")

    school_join_sql = ""
    coalesce_sql = f"c.{org_col}"

    if "school_id" in cols and _table_exists(conn, "schools"):
        # schools.organization_id for committees scoped by school
        school_join_sql = 'LEFT JOIN "schools" s ON s.id = c.school_id'
        coalesce_sql = f"COALESCE(c.{org_col}, s.organization_id)"

    sql = (
        f'SELECT c.id AS committee_id, {coalesce_sql} AS org_id '
        f'FROM "{committees_tbl}" c {school_join_sql}'
    )
    rows = conn.execute(sa.text(sql)).fetchall()
    return [(r[0], r[1]) for r in rows]


def _generate_rows(comm_map: List[Tuple[str, Optional[str]]], n: int) -> List[Dict[str, object]]:
    """Generate meeting rows tied to existing committees; require org_id."""
    if SEED is not None:
        try:
            random.seed(int(SEED))
        except ValueError:
            random.seed(SEED)

    # keep only committees that can yield a valid org_id
    comm_map = [(cid, oid) for cid, oid in comm_map if oid]
    if not comm_map:
        return []

    titles = [
        "Regular Meeting", "Special Meeting", "Planning Session", "Work Session",
        "Public Hearing", "Annual Review", "Budget Workshop", "Policy Discussion",
        "Stakeholder Forum", "Orientation",
    ]
    locations = [
        "District Office, Board Room", "Main Campus, Library", "High School, Room 201",
        "Middle School, Auditorium", "Elementary Campus, MPR", "Virtual (Video Conference)",
    ]
    statuses = ["scheduled", "completed", "cancelled", "postponed"]

    rows: List[Dict[str, object]] = []
    now = datetime.now(timezone.utc)

    for _ in range(n):
        cid, oid = random.choice(comm_map)

        # start within ±60 days, at meeting-ish times
        day_offset = random.randint(-60, 60)
        hour = random.choice([8, 9, 15, 16, 17, 18, 19])
        minute = random.choice([0, 15, 30, 45])
        scheduled_at = (now + timedelta(days=day_offset)).replace(
            hour=hour, minute=minute, second=0, microsecond=0
        )
        duration_min = random.choice([60, 75, 90, 120, 150, 180])
        ends_at = scheduled_at + timedelta(minutes=duration_min)

        title = random.choice(titles)
        if random.random() < 0.25:
            title = f"{title} #{random.randint(2, 12)}"
        status = random.choices(statuses, weights=[7, 2, 0.5, 0.5], k=1)[0]
        is_public = random.random() < 0.8

        rows.append(
            {
                "id": str(uuid.uuid4()),
                "org_id": oid,                 # REQUIRED by meetings schema
                "committee_id": cid,           # included only if column exists
                "title": title,
                "scheduled_at": scheduled_at.isoformat(),
                "starts_at": scheduled_at.isoformat(),  # seed starts_at = scheduled_at
                "ends_at": ends_at.isoformat(),
                "location": random.choice(locations),
                "status": status,
                "is_public": "true" if is_public else "false",
                "stream_url": None,
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
            }
        )
    return rows


def _write_csv(path: str, rows: List[Dict[str, object]]) -> None:
    if not rows:
        with open(path, "w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=["id"]).writeheader()
        return

    fieldnames = list(rows[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def _read_csv(path: str) -> List[Dict[str, object]]:
    with open(path, "r", newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        return list(r)


def _to_bool(v: object) -> bool:
    if isinstance(v, bool):
        return v
    s = (v or "").strip().lower()
    return s in {"1", "true", "t", "yes", "y"}


# ----------------------------- migration -------------------------------------
def upgrade():
    conn = op.get_bind()
    insp = sa.inspect(conn)

    log.info("[meetings] begin population; target rows=%s", DEFAULT_ROW_COUNT)

    committees_tbl = _resolve_table_name(conn, ("committees",))
    if not committees_tbl:
        log.warning("[meetings] committees table not found; skipping.")
        return

    meetings_tbl = _resolve_table_name(conn, ("meetings",))
    if not meetings_tbl:
        log.warning("[meetings] meetings table not found; skipping.")
        return

    # 1) Reference data (committee_id, org_id)
    comm_map = _fetch_committees(conn, committees_tbl)
    if not comm_map:
        log.info("[meetings] No committees with resolvable org_id; nothing to seed.")
        return
    log.info("[meetings] %d committee(s) with org_id", len(comm_map))

    # 2) Generate & write CSV
    rows = _generate_rows(comm_map, DEFAULT_ROW_COUNT)
    csv_path = _csv_path()
    _write_csv(csv_path, rows)
    log.info("[meetings] wrote CSV: %s (rows=%d)", csv_path, len(rows))

    if not rows:
        log.info("[meetings] nothing to insert.")
        return

    # 3) Determine which columns actually exist on meetings, and their types
    cols_info = {c["name"]: c for c in insp.get_columns(meetings_tbl)}

    wanted = [
        "id", "org_id", "committee_id", "title",
        "scheduled_at", "starts_at", "ends_at",
        "location", "status", "is_public", "stream_url",
        "created_at", "updated_at",
    ]
    present = [c for c in wanted if c in cols_info]

    # Drop any *timestamp* columns that aren't really timestamp types
    from sqlalchemy.sql.sqltypes import DateTime as _SQLADateTime, Boolean as _SQLABoolean

    def _is_dt(col: str) -> bool:
        return isinstance(cols_info[col]["type"], _SQLADateTime)

    for tscol in ("created_at", "updated_at", "scheduled_at", "starts_at", "ends_at"):
        if tscol in present and not _is_dt(tscol):
            log.warning(
                "[meetings] '%s' exists but is %s; omitting from seed insert.",
                tscol, cols_info[tscol]["type"]
            )
            present.remove(tscol)

    # 4) Clear table idempotently
    conn.execute(sa.text(f'SELECT 1 FROM "{meetings_tbl}" LIMIT 1'))
    conn.execute(sa.text(f'DELETE FROM "{meetings_tbl}"'))
    log.info("[meetings] table '%s' cleared", meetings_tbl)

    # 5) Build a lightweight table with only present columns for bulk_insert
    def _col_type(col: str):
        t = cols_info[col]["type"]
        if isinstance(t, _SQLADateTime):
            return sa.DateTime(timezone=getattr(t, "timezone", False))
        if isinstance(t, _SQLABoolean):
            return sa.Boolean()
        return sa.Text()

    meetings = sa.table(
        meetings_tbl, *(sa.column(c, _col_type(c)) for c in present)
    )

    # 6) Normalize rows to present columns + types
    data: List[Dict[str, object]] = _read_csv(csv_path)

    def _dt(x: Optional[str]):
        if not x:
            return None
        s = str(x).strip().replace("Z", "")
        return datetime.fromisoformat(s)

    to_insert: List[Dict[str, object]] = []
    for r in data:
        rec: Dict[str, object] = {}
        for c in present:
            if c in {"scheduled_at", "starts_at", "ends_at", "created_at", "updated_at"}:
                rec[c] = _dt(r.get(c))
            elif c == "is_public":
                rec[c] = _to_bool(r.get(c))
            else:
                rec[c] = (r.get(c) or None)
        to_insert.append(rec)

    # 7) Insert in chunks
    CHUNK = 1000
    total = 0
    for i in range(0, len(to_insert), CHUNK):
        batch = to_insert[i:i + CHUNK]
        if not batch:
            continue
        op.bulk_insert(meetings, batch)
        total += len(batch)
        log.info("[meetings] inserted batch %d..%d (batch=%d)", i + 1, i + len(batch), len(batch))

    log.info("[meetings] complete; inserted=%d", total)


def downgrade():
    conn = op.get_bind()
    meetings_tbl = _resolve_table_name(conn, ("meetings",))
    if not meetings_tbl:
        log.warning("[meetings] downgrade: no meetings table found; nothing to delete.")
        return
    conn.execute(sa.text(f'DELETE FROM "{meetings_tbl}"'))
    log.info("[meetings] downgraded; table '%s' cleared (CSV left on disk)", meetings_tbl)
