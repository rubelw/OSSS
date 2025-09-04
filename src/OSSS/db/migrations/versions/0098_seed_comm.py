# src/OSSS/db/migrations/versions/0092_populate_att_evts.py
from __future__ import annotations

import csv
import logging
import os
import random
import uuid
from datetime import date, timedelta, datetime, timezone
from typing import List, Dict, Tuple, Optional

from alembic import op
import sqlalchemy as sa

# ---- Alembic identifiers ----
revision = "0098_seed_comm"
down_revision = "0097_seed_subscriptions"  # update if needed
branch_labels = None
depends_on = None

# ---- Logging ---------------------------------------------------------------
log = logging.getLogger("alembic.runtime.migration")

# ---- Config / helpers ----
CSV_FILENAME = "committees.csv"
DEFAULT_ROW_COUNT = int(os.getenv("COMMITTEE_ROWS", "12"))
SEED = os.getenv("COMMITTEE_SEED")  # e.g. "42"
ORG_CODE = os.getenv("COMMITTEE_ORG_CODE", "05400000")


def _csv_path() -> str:
    """Write/read CSV next to this migration file."""
    return os.path.join(os.path.dirname(__file__), CSV_FILENAME)


def _fetch_one_scalar(conn, sql: str, **params) -> Optional[str]:
    row = conn.execute(sa.text(sql), params).fetchone()
    return row[0] if row else None


def _fetch_org_id(conn) -> str:
    org_id = _fetch_one_scalar(conn, "SELECT id FROM organizations WHERE code = :code", code=ORG_CODE)
    if not org_id:
        raise RuntimeError(
            f"No organization found with code='{ORG_CODE}'. "
            "Required to populate committees."
        )
    return org_id


def _resolve_committees_table_name(conn) -> Optional[str]:
    """
    Return the existing committees table name. Supports both new and legacy names.
    """
    insp = sa.inspect(conn)
    for name in ("committees", "committees"):
        try:
            if insp.has_table(name):
                return name
        except Exception:
            # Fallback for older dialects; Postgres quick check
            if conn.dialect.name == "postgresql":
                ok = conn.execute(sa.text("SELECT to_regclass(:n) IS NOT NULL"), {"n": name}).scalar()
                if ok:
                    return name
    return None


def _generate_rows(org_id: str, n: int) -> List[Dict[str, object]]:
    """
    Generate n committee rows bound to organization_id.
    school_id is left NULL to satisfy ck_committee_scope via organization_id.
    """
    if SEED is not None:
        try:
            random.seed(int(SEED))
        except ValueError:
            random.seed(SEED)

    # Some plausible committee names (extendable)
    base_names = [
        "Curriculum Council",
        "Safety Committee",
        "Technology Advisory",
        "Wellness Committee",
        "Facilities Planning",
        "Equity & Inclusion Council",
        "Finance & Audit",
        "Policy Review Committee",
        "Professional Learning",
        "Community Engagement",
        "Attendance & Truancy",
        "Assessment & Data Team",
        "Special Education Advisory",
        "MTSS / RTI Team",
        "Staff Culture Committee",
        "Family Partnership Council",
    ]

    # Shuffle and extend with suffixes if more rows requested
    random.shuffle(base_names)
    names: List[str] = []
    i = 0
    while len(names) < n:
        base = base_names[i % len(base_names)]
        if i < len(base_names):
            names.append(base)
        else:
            names.append(f"{base} #{(i // len(base_names)) + 2}")
        i += 1

    statuses = ["active", "inactive", "archived"]
    desc_bits = [
        "Meets monthly to review priorities.",
        "Includes staff, admin, and community members.",
        "Focus on continuous improvement and outcomes.",
        "Aligns with strategic plan.",
        "Coordinates with site leadership.",
        "Publishes minutes and recommendations.",
        "Advises cabinet on related initiatives.",
    ]

    now = datetime.now(timezone.utc)
    rows: List[Dict[str, object]] = []
    for nm in names[:n]:
        rows.append(
            {
                "id": str(uuid.uuid4()),
                "organization_id": org_id,
                "school_id": "",  # keep blank in CSV → NULL in DB
                "name": nm,
                "description": " ".join(random.sample(desc_bits, k=random.randint(2, 4))),
                "status": random.choices(statuses, weights=[7, 2, 1], k=1)[0],
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
            }
        )
    return rows


def _write_csv(path: str, rows: List[Dict[str, object]]) -> None:
    fieldnames = [
        "id",
        "organization_id",
        "school_id",
        "name",
        "description",
        "status",
        "created_at",
        "updated_at",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def _read_csv(path: str) -> List[Dict[str, object]]:
    with open(path, "r", newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        return list(r)


def upgrade():
    conn = op.get_bind()

    log.info("[committees] begin population; target rows=%s", DEFAULT_ROW_COUNT)

    # 0) Determine actual target table name (supports legacy installs)
    target_tbl = _resolve_committees_table_name(conn)
    if not target_tbl:
        log.warning("[committees] No committees table found (looked for committees, committees). Skipping.")
        return
    log.info("[committees] using table: %s", target_tbl)

    # 1) Resolve org
    org_id = _fetch_org_id(conn)
    log.info("[committees] using organization_id for code=%s -> %s", ORG_CODE, org_id)

    # 2) Generate & write CSV
    rows = _generate_rows(org_id, DEFAULT_ROW_COUNT)
    csv_path = _csv_path()
    _write_csv(csv_path, rows)
    log.info("[committees] wrote CSV: %s (rows=%d)", csv_path, len(rows))

    # 3) Clear table idempotently
    conn.execute(sa.text(f"DELETE FROM {sa.text(target_tbl).text}"))
    log.info("[committees] table cleared")

    # 4) Read CSV and prepare inserts (type conversion)
    data = _read_csv(csv_path)
    log.info("[committees] read CSV rows=%d", len(data))

    committees_table = sa.table(
        target_tbl,
        sa.column("id", sa.String),
        sa.column("organization_id", sa.String),
        sa.column("school_id", sa.String),
        sa.column("name", sa.Text),
        sa.column("description", sa.Text),
        sa.column("status", sa.Text),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )

    to_insert: List[Dict[str, object]] = []
    for r in data:
        to_insert.append(
            {
                "id": r["id"],
                "organization_id": r["organization_id"] or None,
                "school_id": r.get("school_id") or None,
                "name": r["name"],
                "description": r.get("description") or None,
                "status": r.get("status") or "active",
                "created_at": datetime.fromisoformat(r["created_at"].replace("Z", "")),
                "updated_at": datetime.fromisoformat(r["updated_at"].replace("Z", "")),
            }
        )

    CHUNK = 1000
    total = 0
    for i in range(0, len(to_insert), CHUNK):
        batch = to_insert[i : i + CHUNK]
        op.bulk_insert(committees_table, batch)
        total += len(batch)
        log.info(
            "[committees] inserted batch %d..%d (batch=%d)",
            i + 1, i + len(batch), len(batch)
        )

    log.info("[committees] complete; inserted=%d", total)


def downgrade():
    conn = op.get_bind()
    target_tbl = _resolve_committees_table_name(conn)
    if not target_tbl:
        log.warning("[committees] downgrade: no committees table found; nothing to delete.")
        return
    conn.execute(sa.text(f"DELETE FROM {sa.text(target_tbl).text}"))
    log.info("[committees] downgraded; table cleared (CSV left on disk)")
