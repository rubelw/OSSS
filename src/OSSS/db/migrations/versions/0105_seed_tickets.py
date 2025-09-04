from __future__ import annotations

import csv
import logging
import os
import random
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from alembic import op
import sqlalchemy as sa

# ---- Alembic identifiers ----
revision = "0105_seed_tickets"
down_revision = "0104_seed_ticket_types"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

# --- Config ---
CSV_FILENAME = "tickets.csv"
DEFAULT_ROW_COUNT = int(os.getenv("TICKETS_ROWS", "500"))
SEED = os.getenv("TICKETS_SEED")  # e.g. "42"

STATUSES = ["issued", "checked_in", "void"]


# --- Helpers --------------------------------------------------------------

def _csv_path() -> str:
    return os.path.join(os.path.dirname(__file__), CSV_FILENAME)

def _reset_failed_tx(conn: sa.engine.Connection) -> None:
    """If the connection is in an aborted transaction, issue ROLLBACK."""
    try:
        conn.execute(sa.text("SELECT 1"))
    except Exception:
        try:
            conn.exec_driver_sql("ROLLBACK")
            log.warning("[0105] tickets: detected aborted transaction; issued ROLLBACK")
        except Exception:
            log.exception("[0105] tickets: failed to ROLLBACK aborted transaction")

def _table_exists(conn: sa.engine.Connection, table_name: str) -> bool:
    # Use information_schema to avoid aborting the transaction on missing tables
    sql = sa.text(
        """
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = current_schema()
          AND table_name = :t
        """
    )
    return conn.execute(sql, {"t": table_name}).fetchone() is not None

def _fetch_all_scalar(conn, sql: str) -> List[str]:
    return [r[0] for r in conn.execute(sa.text(sql)).fetchall()]

def _fetch_ticket_types(conn) -> List[Tuple[str, int]]:
    """
    Returns [(ticket_type_id, price_cents)].
    price_cents may not exist on ticket_types in some schemas; fallback to random.
    """
    cols = set(
        conn.execute(
            sa.text(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = current_schema()
                  AND table_name = :t
                """
            ),
            {"t": "ticket_types"},
        ).scalars().all()
    )
    if "price_cents" in cols:
        rows = conn.execute(sa.text("SELECT id, price_cents FROM ticket_types")).fetchall()
        return [(r[0], int(r[1] or 0)) for r in rows]
    rows = conn.execute(sa.text("SELECT id FROM ticket_types")).fetchall()
    return [(r[0], random.choice([0, 500, 1000, 1500, 2000, 2500, 3000])) for r in rows]

def _fetch_orders(conn) -> List[str]:
    # Only used if an order FK column exists on tickets
    if not _table_exists(conn, "orders"):
        return []
    return _fetch_all_scalar(conn, "SELECT id FROM orders")

def _fetch_people(conn) -> List[str]:
    # Optional; link holder_person_id if present on tickets & table exists
    if not _table_exists(conn, "people"):
        return []
    return _fetch_all_scalar(conn, "SELECT id FROM people")

def _resolve_order_fk_column(bind: sa.engine.Connection) -> Optional[str]:
    """
    Discover which tickets.* column references orders (if any).
    """
    meta = sa.MetaData()
    tickets = sa.Table("tickets", meta, autoload_with=bind)
    cols = {c.name for c in tickets.c}

    candidates = [
        "order_id",
        "purchase_id",
        "sales_order_id",
        "order_uuid",
    ]
    for c in candidates:
        if c in cols:
            return c
    # Heuristics
    for c in cols:
        if c.endswith("_order_id") or (c.startswith("order_") and c.endswith("_id")):
            return c
    log.warning("[0105] tickets: no order FK column found; seeding without order linkage.")
    return None

def _existing_ticket_columns(bind: sa.engine.Connection) -> List[str]:
    meta = sa.MetaData()
    t = sa.Table("tickets", meta, autoload_with=bind)
    return [c.name for c in t.c]

def _generate_rows(
    ticket_types: List[Tuple[str, int]],
    orders: List[str],
    people: List[str],
    want: int,
    have_order_fk: bool,
) -> List[Dict[str, object]]:
    if SEED is not None:
        try:
            random.seed(int(SEED))
        except ValueError:
            random.seed(SEED)

    if not ticket_types:
        raise RuntimeError("No ticket_types available. Cannot generate tickets.")

    now = datetime.now(timezone.utc)
    rows: List[Dict[str, object]] = []

    # Keep serial numbers unique per ticket_type
    serial_by_tt: Dict[str, int] = {}

    # Distribute across ticket types uniformly-ish
    for _ in range(want):
        tt_id, price = random.choice(ticket_types)
        serial_by_tt[tt_id] = serial_by_tt.get(tt_id, 0) + 1
        serial_no = serial_by_tt[tt_id]

        status = random.choice(STATUSES)
        issued_at = now - timedelta(days=random.randint(5, 150), hours=random.randint(0, 23))
        checked_in_at: Optional[datetime] = None
        if status == "checked_in":
            # checked-in after issue
            checked_in_at = issued_at + timedelta(hours=random.randint(0, 6))

        holder: Optional[str] = None
        if people and random.random() < 0.6:
            holder = random.choice(people)

        qr_code = None
        if random.random() < 0.8:
            # cheap fake code
            qr_code = uuid.uuid4().hex[:24]

        row = {
            "id": str(uuid.uuid4()),
            "ticket_type_id": tt_id,
            "serial_no": serial_no,
            "price_cents": int(price),
            "holder_person_id": holder,
            "qr_code": qr_code,
            "status": status,
            "issued_at": issued_at.isoformat(),
            "checked_in_at": checked_in_at.isoformat() if checked_in_at else "",
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }

        if have_order_fk and orders:
            row["order_id"] = random.choice(orders)  # key will be renamed later if needed

        rows.append(row)

    return rows

def _write_csv(csv_path: str, rows: List[Dict[str, object]]) -> None:
    # Include superset of possible columns; we'll trim on insert.
    fieldnames = [
        "id",
        "order_id",            # may not exist on table
        "ticket_type_id",
        "serial_no",
        "price_cents",
        "holder_person_id",
        "qr_code",
        "status",
        "issued_at",
        "checked_in_at",
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

# --- Migration ops ------------------------------------------------------------

def upgrade():
    bind = op.get_bind()
    _reset_failed_tx(bind)

    # Reference data
    ticket_types = _fetch_ticket_types(bind)
    event_orders_col = _resolve_order_fk_column(bind)  # name or None
    orders = _fetch_orders(bind) if event_orders_col else []
    people = _fetch_people(bind)

    # Generate rows
    want = DEFAULT_ROW_COUNT
    rows = _generate_rows(
        ticket_types=ticket_types,
        orders=orders,
        people=people,
        want=want,
        have_order_fk=bool(event_orders_col),
    )

    # CSV round-trip (optional but mirrors other seeds)
    csv_path = _csv_path()
    _write_csv(csv_path, rows)
    data = _read_csv(csv_path)

    # Reflect actual tickets table and columns
    _reset_failed_tx(bind)
    meta = sa.MetaData()
    tickets_tbl = sa.Table("tickets", meta, autoload_with=bind)
    cols = set(c.name for c in tickets_tbl.c)

    # Idempotent: clear table before seeding
    _reset_failed_tx(bind)
    bind.execute(sa.text("DELETE FROM tickets"))

    # Prepare rows respecting actual schema
    fixed: List[Dict[str, object]] = []
    for r in data:
        # Map/rename the order column if present and differently named.
        row: Dict[str, object] = {
            "id": r.get("id"),
            "ticket_type_id": r.get("ticket_type_id"),
            "serial_no": int(r["serial_no"]) if (r.get("serial_no") or "").strip() else None,
            "price_cents": int(r["price_cents"]) if (r.get("price_cents") or "").strip() else 0,
            "holder_person_id": (r.get("holder_person_id") or "").strip() or None,
            "qr_code": (r.get("qr_code") or "").strip() or None,
            "status": (r.get("status") or "issued"),
            "issued_at": _parse_dt(r.get("issued_at")),
            "checked_in_at": _parse_dt(r.get("checked_in_at")),
            "created_at": _parse_dt(r.get("created_at")),
            "updated_at": _parse_dt(r.get("updated_at")),
        }

        # If the table actually has an order FK column, ensure we put the value there.
        if event_orders_col:
            row[event_orders_col] = (r.get("order_id") or "").strip() or None

        # Drop any keys not present on the real table
        clean = {k: v for k, v in row.items() if k in cols}
        fixed.append(clean)

    log.info("[0105] tickets: inserting %d rows (columns present: %s)", len(fixed), sorted(cols))
    CHUNK = 1000
    for i in range(0, len(fixed), CHUNK):
        bind.execute(tickets_tbl.insert(), fixed[i : i + CHUNK])

    log.info("[0105] tickets: done.")

def downgrade():
    bind = op.get_bind()
    log.info("[0105] tickets: deleting all rows (downgrade)…")
    bind.execute(sa.text("DELETE FROM tickets"))
