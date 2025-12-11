from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0094"
down_revision = "0093"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "events"

# Inline seed data for events
# Columns: school_id, activity_id, title, summary, starts_at, ends_at,
#          venue, status, attributes, created_at, updated_at, id
SEED_ROWS = [
    {
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "activity_id": "e6626448-82fb-56c2-915e-166743fd5841",
        "title": "Homecoming Pep Rally",
        "summary": (
            "School-wide pep rally to kick off Homecoming week with games, "
            "performances, and class competitions."
        ),
        "starts_at": "2024-09-20T19:00:00Z",
        "ends_at": "2024-09-20T20:30:00Z",
        "venue": "HS Main Gym",
        "status": "scheduled",
        "attributes": {},
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
        "id": "13e28612-f86c-5753-8964-2ed13f37a8b4",
    },
    {
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "activity_id": "e6626448-82fb-56c2-915e-166743fd5841",
        "title": "Homecoming Dance",
        "summary": (
            "Semi-formal evening dance sponsored by Student Council for grades 9–12."
        ),
        "starts_at": "2024-09-22T00:00:00Z",
        "ends_at": "2024-09-22T03:00:00Z",
        "venue": "HS Commons / Cafeteria",
        "status": "scheduled",
        "attributes": {},
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
        "id": "b91e78c6-1eb9-5b03-85ec-11be90bddb60",
    },
    {
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "activity_id": "e6626448-82fb-56c2-915e-166743fd5841",
        "title": "Fall Food Drive Kickoff",
        "summary": (
            "Kickoff assembly and announcement of the annual canned food drive "
            "and classroom competition."
        ),
        "starts_at": "2024-10-07T14:30:00Z",
        "ends_at": "2024-10-07T15:15:00Z",
        "venue": "HS Auditorium",
        "status": "published",
        "attributes": {},
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
        "id": "a00c43d9-dbc3-51a2-83fc-1ba16652c33a",
    },
    {
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "activity_id": "e6626448-82fb-56c2-915e-166743fd5841",
        "title": "Winter Formal",
        "summary": (
            "Student Council-sponsored winter formal dance featuring DJ, "
            "photo booth, and refreshments."
        ),
        "starts_at": "2025-01-18T01:00:00Z",
        "ends_at": "2025-01-18T04:00:00Z",
        "venue": "HS Main Gym",
        "status": "scheduled",
        "attributes": {},
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
        "id": "7d8e9df8-df6c-5bb9-8b81-ade4fc1d969e",
    },
    {
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "activity_id": "e6626448-82fb-56c2-915e-166743fd5841",
        "title": "Student Council Elections Assembly",
        "summary": (
            "Spring assembly to introduce candidates, share speeches, and outline "
            "voting procedures for Student Council elections."
        ),
        "starts_at": "2025-04-10T14:00:00Z",
        "ends_at": "2025-04-10T15:00:00Z",
        "venue": "HS Auditorium",
        "status": "scheduled",
        "attributes": {},
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
        "id": "b5e76d66-de8f-5f58-938e-5ddcd623545c",
    },
]


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion from inline value to appropriate Python/DB value."""
    if raw == "" or raw is None:
        return None

    t = col.type

    # Boolean coercion
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

    # Everything else (UUID, timestamptz, JSONB, etc.) let DB/SQLAlchemy cast
    return raw


def upgrade() -> None:
    """Load seed data for events from inline SEED_ROWS with per-row SAVEPOINTs."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(TABLE_NAME):
        log.warning("Table %s does not exist; skipping seed", TABLE_NAME)
        return

    if not SEED_ROWS:
        log.info("No inline seed rows defined for %s; nothing to insert", TABLE_NAME)
        return

    metadata = sa.MetaData()
    table = sa.Table(TABLE_NAME, metadata, autoload_with=bind)

    inserted = 0

    for raw_row in SEED_ROWS:
        row: dict[str, object] = {}

        for col in table.columns:
            if col.name not in raw_row:
                continue
            raw_val = raw_row[col.name]
            row[col.name] = _coerce_value(col, raw_val)

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

    log.info("Inserted %s inline seed rows into %s", inserted, TABLE_NAME)


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
