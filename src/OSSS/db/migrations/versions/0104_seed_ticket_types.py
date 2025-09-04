from __future__ import annotations

import csv
import logging
import os
import json
import random
import uuid
from datetime import date, timedelta, datetime, timezone
from typing import List, Dict, Tuple, Optional

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
revision = "0104_seed_ticket_types"
down_revision = "0103_seed_orders"  # update if needed
branch_labels = None
depends_on = None

# ---- Logging ---------------------------------------------------------------
log = logging.getLogger("alembic.runtime.migration")

# --- Config knobs ---
CSV_FILENAME = "ticket_types.csv"
DEFAULT_PER_EVENT_MIN = int(os.getenv("TICKET_TYPES_PER_EVENT_MIN", "2"))
DEFAULT_PER_EVENT_MAX = int(os.getenv("TICKET_TYPES_PER_EVENT_MAX", "3"))
SEED = os.getenv("TICKET_TYPES_SEED")  # e.g., "42" for reproducibility

# Price & quantity menus
PRICE_CHOICES = [0, 500, 1000, 1500, 2000, 2500, 3000, 4000, 5000]  # cents
QTY_TOTAL_RANGE = (50, 500)

NAMES = [
    "General Admission",
    "Student",
    "Staff",
    "VIP",
    "Family",
    "Early Bird",
    "Late Entry",
    "Premium",
]

def _csv_path() -> str:
    return os.path.join(os.path.dirname(__file__), CSV_FILENAME)

def _fetch_events(conn) -> List[Tuple[str, Optional[datetime], Optional[datetime]]]:
    """Returns list of (id, starts_at, ends_at) from events."""
    rows = conn.execute(sa.text("SELECT id, starts_at, ends_at FROM events")).fetchall()
    return [(r[0], r[1], r[2]) for r in rows]

def _rand_sales_window(starts_at: Optional[datetime], ends_at: Optional[datetime]) -> Tuple[Optional[datetime], Optional[datetime]]:
    """Choose a plausible sales window relative to the event time."""
    now = datetime.now(timezone.utc)
    base = starts_at or now + timedelta(days=random.randint(7, 60))
    start = base - timedelta(days=random.randint(7, 45), hours=random.randint(0, 10))
    end = (starts_at or base) + timedelta(hours=random.randint(0, 6))
    if random.random() < 0.1:
        end = end + timedelta(hours=random.randint(2, 24))
    if end < start:
        end = start + timedelta(hours=random.randint(1, 8))
    return start, end

def _unique_names_for_event(k: int) -> List[str]:
    pool = NAMES[:]
    random.shuffle(pool)
    if k <= len(pool):
        return pool[:k]
    return pool + [f"Type {i}" for i in range(k - len(pool))]

def _generate_rows(
    events: List[Tuple[str, Optional[datetime], Optional[datetime]]],
    per_event_min: int,
    per_event_max: int,
) -> List[Dict[str, object]]:
    if SEED is not None:
        try:
            random.seed(int(SEED))
        except ValueError:
            random.seed(SEED)

    if not events:
        # No events? Still generate some rows detached from events.
        now = datetime.now(timezone.utc)
        fallback_rows = []
        for _ in range(50):
            name = random.choice(NAMES)
            price = random.choice(PRICE_CHOICES)
            qty_total = random.randint(*QTY_TOTAL_RANGE)
            qty_sold = random.randint(0, qty_total)
            s_start = now - timedelta(days=random.randint(1, 10))
            s_end = s_start + timedelta(days=random.randint(1, 5))
            fallback_rows.append(
                {
                    "id": str(uuid.uuid4()),
                    "event_id": None,  # may be ignored on insert
                    "name": name,
                    "price_cents": price,
                    "quantity_total": qty_total,
                    "quantity_sold": qty_sold,
                    "sales_starts_at": s_start.isoformat(),
                    "sales_ends_at": s_end.isoformat(),
                    "attributes": "",
                    "created_at": now.isoformat(),
                    "updated_at": now.isoformat(),
                }
            )
        return fallback_rows

    rows: List[Dict[str, object]] = []
    now = datetime.now(timezone.utc)

    for (event_id, starts_at, ends_at) in events:
        how_many = random.randint(per_event_min, per_event_max)
        names = _unique_names_for_event(how_many)
        base_start, base_end = _rand_sales_window(starts_at, ends_at)

        for name in names:
            price = random.choice(PRICE_CHOICES)
            qty_total = random.randint(*QTY_TOTAL_RANGE)
            qty_sold = random.randint(0, qty_total)

            s_start = base_start - timedelta(hours=random.randint(0, 24))
            s_end = base_end + timedelta(hours=random.randint(0, 24))
            if s_end < s_start:
                s_end = s_start + timedelta(hours=2)

            attrs: Optional[dict] = None
            if random.random() < 0.45:
                attrs = {
                    "color": random.choice(["blue", "green", "purple", "orange", "red"]),
                    "transferable": random.random() < 0.2,
                    "notes": random.choice(
                        ["", "Limited availability", "Includes merch", "Non-refundable"]
                    ),
                }

            rows.append(
                {
                    "id": str(uuid.uuid4()),
                    "event_id": event_id,
                    "name": name,
                    "price_cents": price,
                    "quantity_total": qty_total,
                    "quantity_sold": qty_sold,
                    "sales_starts_at": s_start.isoformat(),
                    "sales_ends_at": s_end.isoformat(),
                    "attributes": json.dumps(attrs) if attrs is not None else "",
                    "created_at": now.isoformat(),
                    "updated_at": now.isoformat(),
                }
            )

    return rows

def _write_csv(csv_path: str, rows: List[Dict[str, object]]) -> None:
    fieldnames = [
        "id",
        "event_id",
        "name",
        "price_cents",
        "quantity_total",
        "quantity_sold",
        "sales_starts_at",
        "sales_ends_at",
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

def _parse_dt(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    s = s.strip()
    if not s:
        return None
    return datetime.fromisoformat(s.replace("Z", ""))

def _resolve_event_fk_column(bind: sa.engine.Connection) -> Optional[str]:
    """
    Discover which column on ticket_types is the FK to events, if any.
    Returns None when the table has no such column.
    """
    meta = sa.MetaData()
    tt = sa.Table("ticket_types", meta, autoload_with=bind)
    cols = {c.name for c in tt.c}

    for name in ("event_id", "attendance_event_id", "calendar_event_id", "activity_id"):
        if name in cols:
            return name
    for name in cols:
        if name.endswith("_event_id") or (name.startswith("event_") and name.endswith("_id")):
            return name

    log.warning("[0104] ticket_types: no event FK column found; will insert rows without event linkage.")
    return None

def _has_unique_on_name(bind: sa.engine.Connection) -> bool:
    insp = sa.inspect(bind)
    try:
        for u in insp.get_unique_constraints("ticket_types"):
            cols = set(u.get("column_names") or [])
            if cols == {"name"}:
                return True
    except Exception:
        pass
    return False

def upgrade():
    bind = op.get_bind()

    log.info("[0104] ticket_types: fetching events…")
    events = _fetch_events(bind)
    log.info("[0104] ticket_types: %d event(s) found", len(events))

    per_min = DEFAULT_PER_EVENT_MIN
    per_max = max(DEFAULT_PER_EVENT_MAX, per_min)

    log.info("[0104] ticket_types: generating rows (%d..%d per event)…", per_min, per_max)
    rows = _generate_rows(events, per_min, per_max)

    csv_path = _csv_path()
    log.info("[0104] ticket_types: writing CSV -> %s (%d rows)", csv_path, len(rows))
    _write_csv(csv_path, rows)

    log.info("[0104] ticket_types: clearing table for idempotent seed…")
    bind.execute(sa.text("DELETE FROM ticket_types"))

    data = _read_csv(csv_path)

    # Reflect the actual table so native types (JSONB, timestamptz) are honored.
    meta = sa.MetaData()
    ticket_types = sa.Table("ticket_types", meta, autoload_with=bind)

    # FK column (may be None)
    event_fk_col = _resolve_event_fk_column(bind)
    unique_on_name = _has_unique_on_name(bind)

    # Track names to avoid duplicates if there is a unique(name) and no FK present
    seen_names: set[str] = set()

    fixed_rows: List[Dict[str, object]] = []
    for r in data:
        attrs_raw = (r.get("attributes") or "").strip()
        if attrs_raw.lower() in ("", "null", "none"):
            attrs_val = None
        else:
            try:
                attrs_val = json.loads(attrs_raw) if isinstance(attrs_raw, str) else attrs_raw
            except Exception:
                attrs_val = None

        name_val = r["name"]
        if event_fk_col is None and unique_on_name:
            # keep names unique by suffixing a short token derived from event_id when present
            ev = (r.get("event_id") or "")[:8]
            candidate = f"{name_val} ({ev})" if ev else name_val
            # ensure uniqueness in-memory as well
            i = 1
            base = candidate
            while candidate in seen_names:
                i += 1
                candidate = f"{base}-{i}"
            name_val = candidate
            seen_names.add(name_val)

        row = {
            "id": r["id"],
            "name": name_val,
            "price_cents": int(r["price_cents"]),
            "quantity_total": int(r["quantity_total"]),
            "quantity_sold": int(r["quantity_sold"]),
            "sales_starts_at": _parse_dt(r.get("sales_starts_at")),
            "sales_ends_at": _parse_dt(r.get("sales_ends_at")),
            "attributes": attrs_val,
            "created_at": _parse_dt(r.get("created_at")),
            "updated_at": _parse_dt(r.get("updated_at")),
        }

        # Only include event linkage when the column exists
        if event_fk_col:
            row[event_fk_col] = r.get("event_id")

        fixed_rows.append(row)

    log.info("[0104] ticket_types: inserting %d rows…", len(fixed_rows))
    CHUNK = 1000
    for i in range(0, len(fixed_rows), CHUNK):
        batch = fixed_rows[i : i + CHUNK]
        bind.execute(ticket_types.insert(), batch)

    log.info("[0104] ticket_types: done.")

def downgrade():
    bind = op.get_bind()
    log.info("[0104] ticket_types: deleting all rows (downgrade)…")
    bind.execute(sa.text("DELETE FROM ticket_types"))
