from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0046"
down_revision = "0045"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "committees"

# Inline seed data (from committees.csv)
SEED_ROWS = [
    {
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
        "organization_id": "c201e5e9-60c0-466f-8f63-aecbf868c420",
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "name": "DCG HS Curriculum Review Committee",
        "description": (
            "Reviews and recommends updates to high school curriculum, courses, and "
            "instructional materials to align with district priorities and state standards."
        ),
        "status": "active",
        "id": "9f682e86-6e28-58d8-8aa7-70136e62f6e8",
    },
    {
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
        "organization_id": "c201e5e9-60c0-466f-8f63-aecbf868c420",
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "name": "DCG HS Safety & Security Committee",
        "description": (
            "Focuses on building safety, emergency procedures, drills, and coordination "
            "with local law enforcement and first responders."
        ),
        "status": "active",
        "id": "f53f259c-55f5-5aa0-a5c2-eb65c16fe6db",
    },
    {
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
        "organization_id": "c201e5e9-60c0-466f-8f63-aecbf868c420",
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "name": "DCG HS Technology Advisory Committee",
        "description": (
            "Advises on classroom technology, 1:1 devices, digital citizenship, and "
            "instructional software adoption."
        ),
        "status": "active",
        "id": "185203d7-b3d7-58f8-bc78-a7088443ff35",
    },
    {
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
        "organization_id": "c201e5e9-60c0-466f-8f63-aecbf868c420",
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "name": "DCG HS Activities & Athletics Committee",
        "description": (
            "Provides input on co-curricular programs, athletics scheduling, facilities "
            "usage, and student participation guidelines."
        ),
        "status": "active",
        "id": "11aeecd8-215f-506f-a6da-9256d4c78807",
    },
    {
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
        "organization_id": "c201e5e9-60c0-466f-8f63-aecbf868c420",
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "name": "DCG HS Equity & Student Voice Committee",
        "description": (
            "Works to improve student belonging, access to programs, and representation "
            "of student voice in school decision-making."
        ),
        "status": "active",
        "id": "498e5734-709d-51c1-80b7-444a0c3f3dbd",
    },
]


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion from inline value to appropriate DB-bound value."""
    if raw == "" or raw is None:
        return None

    t = col.type

    # Boolean handling (if you ever add boolean flags later)
    if isinstance(t, sa.Boolean):
        if isinstance(raw, str):
            v = raw.strip().lower()
            if v in ("true", "t", "1", "yes", "y"):
                return True
            if v in ("false", "f", "0", "no", "n"):
                return False
            log.warning(
                "Invalid boolean for %s.%s: %r; using NULL",
                TABLE_NAME,
                col.name,
                raw,
            )
            return None
        return bool(raw)

    # Let DB cast UUID, timestamptz, etc.
    return raw


def upgrade() -> None:
    """Load seed data for committees from inline SEED_ROWS.

    Each row is inserted inside an explicit nested transaction (SAVEPOINT)
    so a failing row won't abort the whole migration transaction.
    """
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(TABLE_NAME):
        log.warning("Table %s does not exist; skipping seed", TABLE_NAME)
        return

    if not SEED_ROWS:
        log.info("No seed rows defined for %s; skipping", TABLE_NAME)
        return

    metadata = sa.MetaData()
    table = sa.Table(TABLE_NAME, metadata, autoload_with=bind)

    inserted = 0
    for raw_row in SEED_ROWS:
        row: dict[str, object] = {}

        for col in table.columns:
            if col.name not in raw_row:
                # allow server defaults (id from UUIDMixin, created_at/updated_at from ts_cols, etc.)
                continue

            raw_val = raw_row[col.name]
            value = _coerce_value(col, raw_val)
            row[col.name] = value

        if not row:
            continue

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

    log.info("Inserted %s rows into %s from inline seed data", inserted, TABLE_NAME)


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
