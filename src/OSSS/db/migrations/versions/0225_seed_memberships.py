from __future__ import annotations

import csv  # kept for consistency with other migrations, even if unused
import logging
import os

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0225"
down_revision = "0224"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "memberships"
CSV_FILE = None  # seeding from inline data instead of CSV


# Inline seed data:
# committee_id, person_id, role, start_date, end_date, voting_member, created_at, updated_at, id
#
# Using the same committee_id and person_id you provided, but with realistic roles,
# date ranges, and boolean flags.
SEED_ROWS = [
    {
        "committee_id": "9f682e86-6e28-58d8-8aa7-70136e62f6e8",
        "person_id": "a09b6c88-3418-40b5-9f14-77800af409f7",
        "role": "Community Representative (non-voting)",
        "start_date": "2022-07-01",
        "end_date": "2023-06-30",
        "voting_member": False,
        "created_at": "2022-07-01T08:00:00Z",
        "updated_at": "2022-07-01T08:00:00Z",
        "id": "e8d764a6-75d4-580c-98be-2fef46154955",
    },
    {
        "committee_id": "9f682e86-6e28-58d8-8aa7-70136e62f6e8",
        "person_id": "a09b6c88-3418-40b5-9f14-77800af409f7",
        "role": "Board Member",
        "start_date": "2023-07-01",
        "end_date": "2024-06-30",
        "voting_member": True,
        "created_at": "2023-07-01T09:00:00Z",
        "updated_at": "2023-07-01T09:00:00Z",
        "id": "933f0b97-34b7-5cb2-bbba-d60f4dac2e33",
    },
    {
        "committee_id": "9f682e86-6e28-58d8-8aa7-70136e62f6e8",
        "person_id": "a09b6c88-3418-40b5-9f14-77800af409f7",
        "role": "Vice Chair",
        "start_date": "2024-07-01",
        "end_date": "2025-06-30",
        "voting_member": True,
        "created_at": "2024-07-01T09:00:00Z",
        "updated_at": "2024-07-01T09:00:00Z",
        "id": "79d440ac-6d61-5993-a77c-b897b7268cc7",
    },
    {
        "committee_id": "9f682e86-6e28-58d8-8aa7-70136e62f6e8",
        "person_id": "a09b6c88-3418-40b5-9f14-77800af409f7",
        "role": "Committee Chair",
        "start_date": "2025-07-01",
        "end_date": "2026-06-30",
        "voting_member": True,
        "created_at": "2025-07-01T09:00:00Z",
        "updated_at": "2025-07-01T09:00:00Z",
        "id": "4709f2d1-b7a4-5380-b68a-18b63a2b169f",
    },
    {
        "committee_id": "9f682e86-6e28-58d8-8aa7-70136e62f6e8",
        "person_id": "a09b6c88-3418-40b5-9f14-77800af409f7",
        "role": "Ex-officio Member (non-voting)",
        "start_date": "2026-07-01",
        "end_date": "2027-06-30",
        "voting_member": False,
        "created_at": "2026-07-01T09:00:00Z",
        "updated_at": "2026-07-01T09:00:00Z",
        "id": "d6550ccc-1b7b-5365-a559-9453b9c5dbca",
    },
]


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion from inline seed values to appropriate Python/DB values."""
    if raw == "" or raw is None:
        return None

    t = col.type

    # Boolean handling for voting_member
    if isinstance(t, sa.Boolean):
        if isinstance(raw, str):
            v = raw.strip().lower()
            if v in ("true", "t", "1", "yes", "y"):
                return True
            if v in ("false", "f", "0", "no", "n"):
                return False
            log.warning(
                "Invalid boolean for %s.%s: %r; using NULL", TABLE_NAME, col.name, raw
            )
            return None
        return bool(raw)

    # Otherwise, let the DB cast (UUID, date, timestamp, text, etc.)
    return raw


def upgrade() -> None:
    """Load seed data for memberships from inline SEED_ROWS (no CSV)."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(TABLE_NAME):
        log.warning("Table %s does not exist; skipping seed", TABLE_NAME)
        return

    metadata = sa.MetaData()
    table = sa.Table(TABLE_NAME, metadata, autoload_with=bind)

    rows = SEED_ROWS
    if not rows:
        log.info("No inline seed rows defined for %s", TABLE_NAME)
        return

    inserted = 0
    for raw_row in rows:
        row: dict[str, object] = {}

        for col in table.columns:
            if col.name not in raw_row:
                continue
            raw_val = raw_row[col.name]
            value = _coerce_value(col, raw_val)
            row[col.name] = value

        if not row:
            continue

        # Explicit nested transaction (SAVEPOINT)
        nested = bind.begin_nested()
        try:
            bind.execute(table.insert().values(**row))
            nested.commit()
            inserted += 1
        except (IntegrityError, DataError, StatementError) as exc:
            nested.rollback()
            log.warning(
                "Skipping row for %s due to error: %s. Row: %s",
                TABLE_NAME,
                exc,
                raw_row,
            )

    log.info("Inserted %s inline seed rows into %s", inserted, TABLE_NAME)


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
