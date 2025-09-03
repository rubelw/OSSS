# src/OSSS/db/migrations/versions/0092_populate_att_evts.py
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
revision = "0105_seed_tickets"
down_revision = "0104_seed_ticket_types"  # update if needed
branch_labels = None
depends_on = None

# ---- Logging ---------------------------------------------------------------
log = logging.getLogger("alembic.runtime.migration")


# --- Config / knobs ---
CSV_FILENAME = "tickets.csv"
DEFAULT_ROW_COUNT = int(os.getenv("TICKET_ROWS", "500"))
SEED = os.getenv("TICKET_SEED")  # e.g. "42" for reproducibility

# time window for issued_at
DAYS_BACK = int(os.getenv("TICKET_DAYS_BACK", "120"))

# price menu (cents) if you don't want full randomness
PRICE_CHOICES = [0, 500, 1000, 1500, 2000, 2500, 3000, 4500, 5000, 7500]

STATUS_CHOICES = ["issued", "checked_in", "void"]
STATUS_WEIGHTS = [0.70, 0.25, 0.05]  # skew toward issued

QR_PROBABILITY = 0.85  # 85% of rows get a QR token
PERSON_PROBABILITY = 0.70  # 70% of rows get a holder_person_id

def _csv_path() -> str:
    """Write CSV next to this migration file."""
    return os.path.join(os.path.dirname(__file__), CSV_FILENAME)

def _fetch_all_scalar(conn, sql: str) -> List[str]:
    return [r[0] for r in conn.execute(sa.text(sql)).fetchall()]

def _fetch_reference_data(conn):
    order_ids = _fetch_all_scalar(conn, "SELECT id FROM orders")
    type_ids  = _fetch_all_scalar(conn, "SELECT id FROM ticket_types")
    person_ids = _fetch_all_scalar(conn, "SELECT id FROM persons")
    return order_ids, type_ids, person_ids

def _rand_time(window_days: int) -> datetime:
    now = datetime.now(timezone.utc)
    delta = timedelta(days=random.randint(0, max(1, window_days)), seconds=random.randint(0, 86400))
    return now - delta

def _maybe_qr() -> Optional[str]:
    return uuid.uuid4().hex[:24] if random.random() < QR_PROBABILITY else None

def _generate_rows(
    order_ids: List[str],
    type_ids: List[str],
    person_ids: List[str],
    max_rows: int,
) -> List[Dict[str, object]]:
    """
    Generate tickets with constraints:
      - (ticket_type_id, serial_no) is UNIQUE (uq_ticket_serial_per_type)
      - price_cents >= 0
      - status ∈ {issued, checked_in, void}
      - checked_in_at only when status == 'checked_in' and after issued_at
    """
    if SEED is not None:
        try:
            random.seed(int(SEED))
        except ValueError:
            random.seed(SEED)

    if not order_ids:
        raise RuntimeError("No orders found. Cannot generate tickets.")
    if not type_ids:
        raise RuntimeError("No ticket_types found. Cannot generate tickets.")
    # persons may be empty; holder_person_id is optional

    rows: List[Dict[str, object]] = []

    # Track next serial number per ticket_type_id to ensure uniqueness
    next_serial: Dict[str, int] = {tid: 1 for tid in type_ids}

    # distribute ticket generation roughly evenly among ticket types
    for _ in range(max_rows):
        ticket_type_id = random.choice(type_ids)
        serial_no = next_serial[ticket_type_id]
        next_serial[ticket_type_id] = serial_no + 1

        order_id = random.choice(order_ids)

        price_cents = random.choice(PRICE_CHOICES)
        status = random.choices(STATUS_CHOICES, weights=STATUS_WEIGHTS, k=1)[0]

        issued_at = _rand_time(DAYS_BACK)

        checked_in_at: Optional[datetime] = None
        if status == "checked_in":
            # ensure after issued_at by 0-3 hours
            checked_in_at = issued_at + timedelta(minutes=random.randint(1, 180))

        holder_person_id: Optional[str] = None
        if person_ids and random.random() < PERSON_PROBABILITY:
            holder_person_id = random.choice(person_ids)

        now = datetime.now(timezone.utc)

        rows.append(
            {
                "id": str(uuid.uuid4()),
                "order_id": order_id,
                "ticket_type_id": ticket_type_id,
                "serial_no": serial_no,
                "price_cents": price_cents,
                "holder_person_id": holder_person_id or "",
                "qr_code": _maybe_qr() or "",
                "status": status,
                "issued_at": issued_at.isoformat(),
                "checked_in_at": checked_in_at.isoformat() if checked_in_at else "",
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
            }
        )

    return rows

def _write_csv(csv_path: str, rows: List[Dict[str, object]]) -> None:
    fieldnames = [
        "id",
        "order_id",
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

def upgrade():
    conn = op.get_bind()

    log.info("[0102] tickets: fetching reference data…")
    order_ids, type_ids, person_ids = _fetch_reference_data(conn)
    log.info("[0102] tickets: %d orders, %d ticket_types, %d persons", len(order_ids), len(type_ids), len(person_ids))

    log.info("[0102] tickets: generating %d rows…", DEFAULT_ROW_COUNT)
    rows = _generate_rows(order_ids, type_ids, person_ids, DEFAULT_ROW_COUNT)

    csv_path = _csv_path()
    log.info("[0102] tickets: writing CSV at %s (%d rows)…", csv_path, len(rows))
    _write_csv(csv_path, rows)

    # Be idempotent within this migration: clear table, then insert.
    log.info("[0102] tickets: clearing table…")
    conn.execute(sa.text("DELETE FROM tickets"))

    data = _read_csv(csv_path)

    table = sa.table(
        "tickets",
        sa.column("id", sa.String),
        sa.column("order_id", sa.String),
        sa.column("ticket_type_id", sa.String),
        sa.column("serial_no", sa.Integer),
        sa.column("price_cents", sa.Integer),
        sa.column("holder_person_id", sa.String),
        sa.column("qr_code", sa.String),
        sa.column("status", sa.String),
        sa.column("issued_at", sa.DateTime(timezone=True)),
        sa.column("checked_in_at", sa.DateTime(timezone=True)),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )

    # Convert types
    to_insert = []
    for r in data:
        to_insert.append(
            {
                "id": r["id"],
                "order_id": r["order_id"],
                "ticket_type_id": r["ticket_type_id"],
                "serial_no": int(r["serial_no"]),
                "price_cents": int(r["price_cents"]),
                "holder_person_id": (r.get("holder_person_id") or None),
                "qr_code": (r.get("qr_code") or None),
                "status": r["status"],
                "issued_at": datetime.fromisoformat(r["issued_at"]),
                "checked_in_at": datetime.fromisoformat(r["checked_in_at"]) if (r.get("checked_in_at") or "").strip() else None,
                "created_at": datetime.fromisoformat(r["created_at"]),
                "updated_at": datetime.fromisoformat(r["updated_at"]),
            }
        )

    log.info("[0102] tickets: inserting %d rows…", len(to_insert))
    CHUNK = 1000
    for i in range(0, len(to_insert), CHUNK):
        op.bulk_insert(table, to_insert[i : i + CHUNK])
    log.info("[0102] tickets: done.")

def downgrade():
    conn = op.get_bind()
    log.info("[0102] tickets: deleting all rows (downgrade)…")
    conn.execute(sa.text("DELETE FROM tickets"))