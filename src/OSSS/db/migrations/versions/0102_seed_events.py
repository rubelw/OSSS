from __future__ import annotations

import csv
import logging
import os
import random
import json
import uuid
from datetime import date, timedelta, datetime, timezone
from typing import List, Dict, Tuple

from alembic import op
import sqlalchemy as sa


# Pull the shims from your app (preferred)
try:
    from app.models.base import GUID, JSONB, TSVectorType  # GUID/JSONB TypeDecorator; TSVectorType for PG tsvector
except Exception:
    import uuid
    from sqlalchemy.types import TypeDecorator, CHAR

    class GUID(TypeDecorator):
        impl = CHAR
        cache_ok = True
        def load_dialect_impl(self, dialect):
            if dialect.name == "postgresql":
                from sqlalchemy.dialects.postgresql import UUID as PGUUID
                return dialect.type_descriptor(PGUUID(as_uuid=True))
            return dialect.type_descriptor(sa.CHAR(36))
        def process_bind_param(self, value, dialect):
            if value is None:
                return None
            if not isinstance(value, uuid.UUID):
                value = uuid.UUID(str(value))
            return str(value)
        def process_result_value(self, value, dialect):
            return None if value is None else uuid.UUID(value)

    try:
        from sqlalchemy.dialects.postgresql import JSONB as PGJSONB
    except Exception:
        PGJSONB = None

    class JSONB(TypeDecorator):
        impl = sa.JSON
        cache_ok = True
        def load_dialect_impl(self, dialect):
            if dialect.name == "postgresql" and PGJSONB is not None:
                return dialect.type_descriptor(PGJSONB())
            return dialect.type_descriptor(sa.JSON())

    try:
        from sqlalchemy.dialects.postgresql import TSVECTOR as PG_TSVECTOR
        class TSVectorType(PG_TSVECTOR):
            pass
    except Exception:
        class TSVectorType(sa.Text):
            pass

# ---- Alembic identifiers ----
revision = "0102_seed_events"
down_revision = "0101_seed_mtg_doc"  # update if needed
branch_labels = None
depends_on = None

# ---- Logging ---------------------------------------------------------------
log = logging.getLogger("alembic.runtime.migration")

# --- Config knobs ---
CSV_FILENAME = "events.csv"
DEFAULT_ROW_COUNT = int(os.getenv("EVENT_ROWS", "400"))
SEED = os.getenv("EVENT_SEED")  # e.g., "42" for reproducibility
DAYS_BACK = int(os.getenv("EVENT_DAYS_BACK", "60"))
DAYS_FORWARD = int(os.getenv("EVENT_DAYS_FWD", "120"))

STATUS_CHOICES = ["draft", "published", "cancelled"]
STATUS_WEIGHTS = [0.25, 0.65, 0.10]

VENUES = [
    "Main Auditorium",
    "Gymnasium",
    "Cafeteria",
    "Library",
    "Room 101",
    "Board Room",
    "Field A",
    "Community Hall",
]

TITLE_FRAGMENTS = [
    "Parent Night",
    "Science Fair",
    "Board Meeting",
    "Drama Club Performance",
    "Math Olympiad",
    "Career Day",
    "Open House",
    "Athletics Awards",
    "Choir Concert",
    "STEM Expo",
]

def _csv_path() -> str:
    return os.path.join(os.path.dirname(__file__), CSV_FILENAME)

def _fetch_all_scalar(conn, sql: str) -> List[str]:
    return [r[0] for r in conn.execute(sa.text(sql)).fetchall()]

def _fetch_reference_data(conn):
    school_ids = _fetch_all_scalar(conn, "SELECT id FROM schools")
    activity_ids = _fetch_all_scalar(conn, "SELECT id FROM activities")
    return school_ids, activity_ids

def _rand_dt() -> datetime:
    """Pick a start datetime in [-DAYS_BACK, +DAYS_FORWARD], then end after start."""
    now = datetime.now(timezone.utc)
    delta_days = random.randint(-DAYS_BACK, DAYS_FORWARD)
    start = now + timedelta(days=delta_days, minutes=random.randint(0, 24*60))
    return start

def _maybe_end_after(start: datetime) -> Optional[datetime]:
    if random.random() < 0.85:
        return start + timedelta(minutes=random.randint(30, 240))
    return None

def _maybe_activity(activity_ids: List[str]) -> Optional[str]:
    if activity_ids and random.random() < 0.7:
        return random.choice(activity_ids)
    return None

def _rand_title() -> str:
    a = random.choice(TITLE_FRAGMENTS)
    b = random.choice(["", " & Info Session", " – Community", " (K-8)", " 2025", " – Evening"])
    return f"{a}{b}".strip()

def _rand_summary() -> Optional[str]:
    if random.random() < 0.75:
        return random.choice([
            "All families welcome.",
            "Join us for an evening of learning and celebration.",
            "Public meeting—agenda to be published.",
            "Student-led event featuring exhibitions and performances.",
            "Information session with Q&A.",
        ])
    return None

def _rand_venue() -> Optional[str]:
    if random.random() < 0.9:
        return random.choice(VENUES)
    return None

def _rand_attributes() -> Optional[dict]:
    if random.random() < 0.65:
        return {
            "featured": random.random() < 0.25,
            "color": random.choice(["blue", "green", "purple", "orange", "red"]),
            "tags": random.sample(
                ["family", "students", "staff", "community", "music", "sports", "academics"],
                k=random.randint(1, 3),
            ),
        }
    return None

def _generate_rows(
    school_ids: List[str],
    activity_ids: List[str],
    max_rows: int,
) -> List[Dict[str, object]]:
    """
    Generate rows:
      - school_id: required (FK)
      - activity_id: optional (FK)
      - starts_at <= ends_at (if ends_at present)
      - status in {draft,published,cancelled}
      - attributes: JSON (serialized to CSV)
    """
    if SEED is not None:
        try:
            random.seed(int(SEED))
        except ValueError:
            random.seed(SEED)

    if not school_ids:
        raise RuntimeError("No schools found. Cannot generate events.")

    rows: List[Dict[str, object]] = []
    for _ in range(max_rows):
        school_id = random.choice(school_ids)
        activity_id = _maybe_activity(activity_ids)
        starts_at = _rand_dt()
        ends_at = _maybe_end_after(starts_at)
        status = random.choices(STATUS_CHOICES, weights=STATUS_WEIGHTS, k=1)[0]

        attrs = _rand_attributes()

        now = datetime.now(timezone.utc)

        rows.append(
            {
                "id": str(uuid.uuid4()),
                "school_id": school_id,
                "activity_id": activity_id or "",
                "title": _rand_title(),
                "summary": _rand_summary() or "",
                "starts_at": starts_at.isoformat(),
                "ends_at": ends_at.isoformat() if ends_at else "",
                "venue": _rand_venue() or "",
                "status": status,
                "attributes": json.dumps(attrs) if attrs is not None else "",
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
            }
        )

    return rows

def _write_csv(csv_path: str, rows: List[Dict[str, object]]) -> None:
    fieldnames = [
        "id",
        "school_id",
        "activity_id",
        "title",
        "summary",
        "starts_at",
        "ends_at",
        "venue",
        "status",
        "attributes",
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

    log.info("[0103] events: fetching reference data…")
    school_ids, activity_ids = _fetch_reference_data(conn)
    log.info("[0103] events: %d schools, %d activities", len(school_ids), len(activity_ids))

    log.info("[0103] events: generating %d rows…", DEFAULT_ROW_COUNT)
    rows = _generate_rows(school_ids, activity_ids, DEFAULT_ROW_COUNT)

    csv_path = _csv_path()
    log.info("[0103] events: writing CSV at %s (%d rows)…", csv_path, len(rows))
    _write_csv(csv_path, rows)

    # Idempotent behavior: clear table, then insert generated rows
    log.info("[0103] events: clearing table…")
    conn.execute(sa.text("DELETE FROM events"))

    data = _read_csv(csv_path)

    table = sa.table(
        "events",
        sa.column("id", sa.String),
        sa.column("school_id", sa.String),
        sa.column("activity_id", sa.String),
        sa.column("title", sa.String),
        sa.column("summary", sa.Text),
        sa.column("starts_at", sa.DateTime(timezone=True)),
        sa.column("ends_at", sa.DateTime(timezone=True)),
        sa.column("venue", sa.String),
        sa.column("status", sa.String),
        sa.column("attributes", JSONB),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )

    to_insert = []
    for r in data:
        attrs_raw = (r.get("attributes") or "").strip()
        attrs_val = json.loads(attrs_raw) if attrs_raw else None

        to_insert.append(
            {
                "id": r["id"],
                "school_id": r["school_id"],
                "activity_id": (r.get("activity_id") or None),
                "title": r["title"],
                "summary": (r.get("summary") or None),
                "starts_at": datetime.fromisoformat(r["starts_at"]),
                "ends_at": datetime.fromisoformat(r["ends_at"]) if (r.get("ends_at") or "").strip() else None,
                "venue": (r.get("venue") or None),
                "status": r["status"],
                "attributes": attrs_val,
                "created_at": datetime.fromisoformat(r["created_at"]),
                "updated_at": datetime.fromisoformat(r["updated_at"]),
            }
        )

    log.info("[0103] events: inserting %d rows…", len(to_insert))
    CHUNK = 1000
    for i in range(0, len(to_insert), CHUNK):
        op.bulk_insert(table, to_insert[i : i + CHUNK])

    log.info("[0103] events: done.")

def downgrade():
    conn = op.get_bind()
    log.info("[0103] events: deleting all rows (downgrade)…")
    conn.execute(sa.text("DELETE FROM events"))