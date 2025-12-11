from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0203"
down_revision = "0202"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "fan_pages"

# Inline seed rows with realistic fan-facing content
# Columns: title, content, created_at, updated_at, school_id, id
SEED_ROWS = [
    {
        "title": "Game Day Information",
        "content": (
            "Find everything you need to know before you arrive on campus for game day. "
            "Gates open 60 minutes prior to kickoff. Digital tickets will be scanned at the main "
            "entrance. Clear bags only are permitted in the stadium. Concession stands accept "
            "credit/debit cards and mobile payments."
        ),
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "id": "dc8fc2c7-2500-5524-a347-909ccd8e9592",
    },
    {
        "title": "Season Tickets & Passes",
        "content": (
            "Support our student-athletes all year long with a season ticket or all-sports pass. "
            "Season tickets include reserved seating for all regular-season home football games. "
            "All-sports passes include admission to regular-season home events across all sports. "
            "Contact the activities office for family packages and staff discounts."
        ),
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "id": "e66197e0-854a-5271-8554-76811c463ce7",
    },
    {
        "title": "Booster Club",
        "content": (
            "The Booster Club partners with our athletics and activities programs to provide extra "
            "resources for equipment, uniforms, travel, and special projects. Memberships are open "
            "to parents, alumni, and community members. Join us to volunteer at events, work "
            "concessions, and help create the best possible experience for our student-athletes."
        ),
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "id": "7d9e9744-feb5-5e6b-8840-d3717b56dcae",
    },
    {
        "title": "Student Section Guidelines",
        "content": (
            "Our student section plays a huge role in creating a positive home-field advantage. "
            "We ask students to demonstrate sportsmanship at all times, follow theme night "
            "guidelines, and remain in designated areas during the game. Signs must be school-appropriate "
            "and may not block the view of other fans. Noise makers are allowed unless restricted by officials."
        ),
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "id": "23840a0a-7f2e-54f0-90eb-38a7a315f066",
    },
    {
        "title": "Athletic Hall of Fame",
        "content": (
            "The Athletic Hall of Fame recognizes former student-athletes, coaches, and contributors "
            "who have made a lasting impact on our programs. Nominations are accepted year-round and "
            "reviewed annually by the selection committee. Inductees are honored at a home football "
            "game each fall and featured on displays in the activities lobby."
        ),
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "id": "da65c435-c4f5-54fb-ae66-b753effd0abe",
    },
]


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion from inline values to appropriate Python/DB values."""
    if raw == "" or raw is None:
        return None

    t = col.type

    # Boolean needs special handling because SQLAlchemy is strict
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

    # Otherwise, pass raw through and let DB cast (TEXT, UUID, timestamptz, etc.)
    return raw


def upgrade() -> None:
    """Load seed data for fan_pages from inline SEED_ROWS.

    Each row is inserted inside an explicit nested transaction (SAVEPOINT)
    so a failing row won't abort the whole migration transaction.
    """
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
