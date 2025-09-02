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
revision = "0097_seed_subscriptions"
down_revision = "0096_seed_channels"  # update if needed
branch_labels = None
depends_on = None

# ---- Logging ---------------------------------------------------------------
log = logging.getLogger("alembic.runtime.migration")


# --- Config knobs ---
CSV_FILENAME = "subscriptions.csv"

# Target rows (upper bound). Real cap is limited by distinct (channel x principals).
DEFAULT_ROW_COUNT = int(os.getenv("SUBSCRIPTION_ROWS", "1500"))

# RNG seed for reproducible runs (unset for true randomness)
SEED = os.getenv("SUBSCRIPTION_SEED")  # e.g. "42"

# Weighted preference among available principal types (only used if that type exists)
DEFAULT_TYPE_WEIGHTS = {
    "user": 0.75,
    "group": 0.20,
    "role": 0.05,
}

# --- Helpers -------------------------------------------------------------------

def _csv_path() -> str:
    """Write CSV next to this migration file."""
    return os.path.join(os.path.dirname(__file__), CSV_FILENAME)

def _fetch_all_scalar(conn, sql: str) -> List[str]:
    return [r[0] for r in conn.execute(sa.text(sql)).fetchall()]

def _table_exists(conn, table_name: str) -> bool:
    try:
        conn.execute(sa.text(f"SELECT 1 FROM {table_name} LIMIT 1"))
        return True
    except Exception:
        return False

def _fetch_reference_data(conn):
    # Required: channels
    channels = _fetch_all_scalar(conn, "SELECT id FROM channels")
    if not channels:
        raise RuntimeError("No channels found. Cannot populate subscriptions.")

    # Optional principal sources (we only use the ones that exist/have rows)
    principals: Dict[str, List[str]] = {}

    if _table_exists(conn, "users"):
        users = _fetch_all_scalar(conn, "SELECT id FROM users")
        if users:
            principals["user"] = users

    if _table_exists(conn, "groups"):
        groups = _fetch_all_scalar(conn, "SELECT id FROM groups")
        if groups:
            principals["group"] = groups

    if _table_exists(conn, "roles"):
        roles = _fetch_all_scalar(conn, "SELECT id FROM roles")
        if roles:
            principals["role"] = roles

    if not principals:
        raise RuntimeError(
            "No principals found. Expected one or more of (users, groups, roles) tables to contain rows."
        )

    return channels, principals

def _choose_type(weights: Dict[str, float]) -> str:
    # Weighted choice among available principal types
    total = sum(weights.values())
    r = random.random() * total
    acc = 0.0
    for t, w in weights.items():
        acc += w
        if r <= acc:
            return t
    # fallback (numerical imprecision)
    return next(iter(weights.keys()))

def _normalize_weights(avail_types: List[str]) -> Dict[str, float]:
    # Keep only available types and renormalize weights
    subset = {k: v for k, v in DEFAULT_TYPE_WEIGHTS.items() if k in avail_types}
    if not subset:
        # In practice shouldn't happen; but guard anyway
        return {avail_types[0]: 1.0}
    s = sum(subset.values())
    return {k: (v / s if s else 1.0 / len(subset)) for k, v in subset.items()}

def _generate_rows(
    channel_ids: List[str],
    principals: Dict[str, List[str]],
    max_rows: int,
) -> List[Dict[str, object]]:
    """
    Generate unique subscriptions consistent with uq_subscriptions_tuple:
    (channel_id, principal_type, principal_id)
    """
    if SEED is not None:
        try:
            random.seed(int(SEED))
        except ValueError:
            random.seed(SEED)

    if not channel_ids:
        raise RuntimeError("No channels to subscribe against.")
    avail_types = sorted(principals.keys())
    weights = _normalize_weights(avail_types)

    total_principals = sum(len(principals[t]) for t in avail_types)
    theoretical_max = len(channel_ids) * total_principals
    target = min(max_rows, theoretical_max)

    unique = set()
    rows: List[Dict[str, object]] = []
    now = datetime.now(timezone.utc)

    log.info(
        "[subscriptions] generating rows; channels=%d, principals={%s}, target=%d (cap=%d)",
        len(channel_ids),
        ", ".join(f"{t}:{len(principals[t])}" for t in avail_types),
        target,
        theoretical_max,
    )

    attempts = 0
    max_attempts = target * 10 if target else 1000

    while len(rows) < target and attempts < max_attempts:
        attempts += 1
        ch = random.choice(channel_ids)
        ptype = _choose_type(weights)
        pid = random.choice(principals[ptype])

        key = (ch, ptype, pid)
        if key in unique:
            continue
        unique.add(key)

        rows.append(
            {
                "id": str(uuid.uuid4()),
                "channel_id": ch,
                "principal_type": ptype,
                "principal_id": pid,
                "created_at": now.isoformat(),
            }
        )

    if len(rows) < target:
        log.warning(
            "[subscriptions] generated %d rows < target=%d (uniqueness/data limits).",
            len(rows),
            target,
        )
    else:
        log.info("[subscriptions] generated %d rows.", len(rows))

    return rows

def _write_csv(csv_path: str, rows: List[Dict[str, object]]) -> None:
    fieldnames = ["id", "channel_id", "principal_type", "principal_id", "created_at"]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    log.info("[subscriptions] wrote CSV: %s (rows=%d)", csv_path, len(rows))

def _read_csv(csv_path: str) -> List[Dict[str, object]]:
    with open(csv_path, "r", newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        data = list(r)
    log.info("[subscriptions] read CSV: %s (rows=%d)", csv_path, len(data))
    return data

# --- Migration ops -------------------------------------------------------------

def upgrade():
    conn = op.get_bind()

    # 1) Reference data
    channel_ids, principals = _fetch_reference_data(conn)

    # 2) Generate + write CSV
    rows = _generate_rows(channel_ids, principals, DEFAULT_ROW_COUNT)
    csv_path = _csv_path()
    _write_csv(csv_path, rows)

    # 3) Clear table for idempotent regeneration
    # 🔒 Clear table safely, independent of prior txn state:
    log.info("[subscriptions] clearing table with TRUNCATE CASCADE")
    with op.get_context().autocommit_block():
        conn.execute(sa.text("TRUNCATE TABLE subscriptions RESTART IDENTITY CASCADE"))

    # 4) Read CSV and bulk insert
    data = _read_csv(csv_path)

    subscriptions = sa.table(
        "subscriptions",
        sa.column("id", sa.String),
        sa.column("channel_id", sa.String),
        sa.column("principal_type", sa.String),
        sa.column("principal_id", sa.String),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )

    to_insert = []
    for r in data:
        to_insert.append(
            {
                "id": r["id"],
                "channel_id": r["channel_id"],
                "principal_type": r["principal_type"],
                "principal_id": r["principal_id"],
                "created_at": datetime.fromisoformat(r["created_at"]),
            }
        )

    CHUNK = 1000
    for i in range(0, len(to_insert), CHUNK):
        batch = to_insert[i : i + CHUNK]
        op.bulk_insert(subscriptions, batch)
        log.info("[subscriptions] inserted chunk %d..%d", i, i + len(batch))

    log.info("[subscriptions] finished inserting %d rows into subscriptions.", len(to_insert))


# 🔒 Clear table safely, independent of prior txn state:
def downgrade():
    conn = op.get_bind()
    log.info("[subscriptions] clearing table with TRUNCATE CASCADE")
    with op.get_context().autocommit_block():
        conn.execute(sa.text("TRUNCATE TABLE subscriptions RESTART IDENTITY CASCADE"))
