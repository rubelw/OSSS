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
revision = "0103_seed_orders"
down_revision = "0102_seed_events"  # update if needed
branch_labels = None
depends_on = None

# ---- Logging ---------------------------------------------------------------
log = logging.getLogger("alembic.runtime.migration")

# --- Config knobs ---
CSV_FILENAME = "orders.csv"
# If you prefer a total target, set ORDERS_TOTAL. Otherwise per-event range is used.
ORDERS_TOTAL = os.getenv("ORDERS_TOTAL")  # e.g., "300"
PER_EVENT_MIN = int(os.getenv("ORDERS_PER_EVENT_MIN", "5"))
PER_EVENT_MAX = int(os.getenv("ORDERS_PER_EVENT_MAX", "15"))
SEED = os.getenv("ORDERS_SEED")  # e.g., "42" for reproducibility

# plausible cents and statuses
PRICE_BUCKETS = [0, 500, 1000, 1500, 2000, 2500, 3000, 4500, 6000, 7500, 10000]  # cents
STATUSES = ["pending", "paid", "cancelled", "refunded"]
STATUS_WEIGHTS = [0.15, 0.7, 0.1, 0.05]  # mostly paid

CURRENCIES = ["USD"]  # keep simple, but could add others
EXTREF_PREFIX = "ch_"  # like a charge id feel

def _csv_path() -> str:
    return os.path.join(os.path.dirname(__file__), CSV_FILENAME)

def _fetch_reference_data(conn) -> Tuple[List[str], List[str]]:
    """Return (event_ids, user_ids). Users may be empty; column is nullable."""
    events = [r[0] for r in conn.execute(sa.text("SELECT id FROM events")).fetchall()]
    users  = [r[0] for r in conn.execute(sa.text("SELECT id FROM users")).fetchall()]
    return events, users

def _random_external_ref() -> str:
    return EXTREF_PREFIX + uuid.uuid4().hex[:22]

def _pick_status() -> str:
    # weighted choice
    r = random.random()
    acc = 0.0
    for s, w in zip(STATUSES, STATUS_WEIGHTS):
        acc += w
        if r <= acc:
            return s
    return STATUSES[-1]

def _maybe_attrs() -> Optional[dict]:
    if random.random() < 0.35:
        return {
            "source": random.choice(["web", "mobile", "pos"]),
            "promo": random.choice(["", "WELCOME10", "FALL25", "EARLYBIRD"]),
            "notes": random.choice(["", "Gift purchase", "Employee purchase", ""]),
        }
    return None

def _generate_rows(
    event_ids: List[str],
    user_ids: List[str],
) -> List[Dict[str, object]]:
    if SEED is not None:
        try:
            random.seed(int(SEED))
        except ValueError:
            random.seed(SEED)

    if not event_ids:
        raise RuntimeError("No events found. Cannot seed orders.")

    now = datetime.now(timezone.utc)
    rows: List[Dict[str, object]] = []

    # Determine how many orders to make
    if ORDERS_TOTAL:
        try:
            total = int(ORDERS_TOTAL)
        except ValueError:
            total = 200
        for _ in range(max(total, 0)):
            ev = random.choice(event_ids)
            purchaser = random.choice(user_ids) if (user_ids and random.random() < 0.8) else None
            status = _pick_status()
            total_cents = random.choice(PRICE_BUCKETS)
            currency = random.choice(CURRENCIES)
            extref = _random_external_ref() if status in ("paid", "refunded") and random.random() < 0.75 else None
            attrs = _maybe_attrs()

            created = now - timedelta(days=random.randint(0, 90), hours=random.randint(0, 12))
            updated = created + timedelta(minutes=random.randint(0, 500))

            rows.append(
                {
                    "id": str(uuid.uuid4()),
                    "event_id": ev,
                    "purchaser_user_id": purchaser or "",
                    "total_cents": total_cents,
                    "currency": currency,
                    "status": status,
                    "external_ref": extref or "",
                    "attributes": json.dumps(attrs) if attrs is not None else "",
                    "created_at": created.isoformat(),
                    "updated_at": updated.isoformat(),
                }
            )
    else:
        # per-event generation
        for ev in event_ids:
            how_many = random.randint(PER_EVENT_MIN, max(PER_EVENT_MAX, PER_EVENT_MIN))
            for _ in range(how_many):
                purchaser = random.choice(user_ids) if (user_ids and random.random() < 0.8) else None
                status = _pick_status()
                total_cents = random.choice(PRICE_BUCKETS)
                currency = random.choice(CURRENCIES)
                extref = _random_external_ref() if status in ("paid", "refunded") and random.random() < 0.75 else None
                attrs = _maybe_attrs()

                now_local = datetime.now(timezone.utc)
                created = now_local - timedelta(days=random.randint(0, 90), hours=random.randint(0, 12))
                updated = created + timedelta(minutes=random.randint(0, 500))

                rows.append(
                    {
                        "id": str(uuid.uuid4()),
                        "event_id": ev,
                        "purchaser_user_id": purchaser or "",
                        "total_cents": total_cents,
                        "currency": currency,
                        "status": status,
                        "external_ref": extref or "",
                        "attributes": json.dumps(attrs) if attrs is not None else "",
                        "created_at": created.isoformat(),
                        "updated_at": updated.isoformat(),
                    }
                )

    return rows

def _write_csv(csv_path: str, rows: List[Dict[str, object]]) -> None:
    fieldnames = [
        "id",
        "event_id",
        "purchaser_user_id",
        "total_cents",
        "currency",
        "status",
        "external_ref",
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

    log.info("[0105] orders: fetching reference data…")
    event_ids, user_ids = _fetch_reference_data(conn)
    log.info("[0105] orders: %d event(s), %d user(s)", len(event_ids), len(user_ids))

    log.info("[0105] orders: generating rows…")
    rows = _generate_rows(event_ids, user_ids)

    csv_path = _csv_path()
    log.info("[0105] orders: writing CSV -> %s (%d rows)", csv_path, len(rows))
    _write_csv(csv_path, rows)

    log.info("[0105] orders: clearing table for idempotent seed…")
    conn.execute(sa.text("DELETE FROM orders"))

    data = _read_csv(csv_path)

    orders_tbl = sa.table(
        "orders",
        sa.column("id", sa.String),
        sa.column("event_id", sa.String),
        sa.column("purchaser_user_id", sa.String),
        sa.column("total_cents", sa.Integer),
        sa.column("currency", sa.String),
        sa.column("status", sa.String),
        sa.column("external_ref", sa.String),
        sa.column("attributes", JSONB),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )

    to_insert: List[Dict[str, object]] = []
    for r in data:
        attrs_raw = (r.get("attributes") or "").strip()
        attrs_val = json.loads(attrs_raw) if attrs_raw else None
        purchaser = (r.get("purchaser_user_id") or "").strip() or None
        extref = (r.get("external_ref") or "").strip() or None

        to_insert.append(
            {
                "id": r["id"],
                "event_id": r["event_id"],
                "purchaser_user_id": purchaser,
                "total_cents": int(r["total_cents"]),
                "currency": r.get("currency") or "USD",
                "status": r.get("status") or "pending",
                "external_ref": extref,
                "attributes": attrs_val,
                "created_at": datetime.fromisoformat(r["created_at"]),
                "updated_at": datetime.fromisoformat(r["updated_at"]),
            }
        )

    log.info("[0105] orders: inserting %d rows…", len(to_insert))
    CHUNK = 1000
    for i in range(0, len(to_insert), CHUNK):
        op.bulk_insert(orders_tbl, to_insert[i : i + CHUNK])

    log.info("[0105] orders: done.")

def downgrade():
    conn = op.get_bind()
    log.info("[0105] orders: deleting all rows (downgrade)…")
    conn.execute(sa.text("DELETE FROM orders"))