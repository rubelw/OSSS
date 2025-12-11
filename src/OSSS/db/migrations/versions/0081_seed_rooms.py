from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0081"
down_revision = "0080"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "rooms"

SEED_ROWS = [
    # DCG High School
    {
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "name": "HS-101 English Classroom",
        "capacity": 28,
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
        "id": "fb53bee7-1426-5dab-b37b-b0964de845f5",
    },
    {
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "name": "HS-102 Algebra Classroom",
        "capacity": 30,
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
        "id": "e5b43950-4e50-54a4-980e-e42e5aef69f3",
    },
    {
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "name": "HS-201 Biology Lab",
        "capacity": 24,
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
        "id": "47a078ce-cf6a-59fd-a77b-2b664daf40ae",
    },
    {
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "name": "HS-Main Gymnasium",
        "capacity": 400,
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
        "id": "3335cc8e-5957-51ed-bf68-12d945e7b6b8",
    },
    {
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "name": "HS-Auditorium",
        "capacity": 600,
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
        "id": "6b3f8b22-c7cd-54d4-a938-f9363c4dc404",
    },

    # DCG Middle School
    {
        "school_id": "119caaef-ef97-5364-b179-388e108bd40d",
        "name": "MS-201 Language Arts Classroom",
        "capacity": 26,
        "created_at": "2024-01-01T06:00:00Z",
        "updated_at": "2024-01-01T06:00:00Z",
        "id": "0a1a3f70-2f3c-5a1a-9b33-aaaaaaaaaaa1",
    },
    {
        "school_id": "119caaef-ef97-5364-b179-388e108bd40d",
        "name": "MS-202 Math Classroom",
        "capacity": 28,
        "created_at": "2024-01-01T07:00:00Z",
        "updated_at": "2024-01-01T07:00:00Z",
        "id": "0a1a3f70-2f3c-5a1a-9b33-aaaaaaaaaaa2",
    },
    {
        "school_id": "119caaef-ef97-5364-b179-388e108bd40d",
        "name": "MS-301 Science Lab",
        "capacity": 24,
        "created_at": "2024-01-01T08:00:00Z",
        "updated_at": "2024-01-01T08:00:00Z",
        "id": "0a1a3f70-2f3c-5a1a-9b33-aaaaaaaaaaa3",
    },
    {
        "school_id": "119caaef-ef97-5364-b179-388e108bd40d",
        "name": "MS-Gym",
        "capacity": 250,
        "created_at": "2024-01-01T09:00:00Z",
        "updated_at": "2024-01-01T09:00:00Z",
        "id": "0a1a3f70-2f3c-5a1a-9b33-aaaaaaaaaaa4",
    },
    {
        "school_id": "119caaef-ef97-5364-b179-388e108bd40d",
        "name": "MS-Cafeteria",
        "capacity": 300,
        "created_at": "2024-01-01T10:00:00Z",
        "updated_at": "2024-01-01T10:00:00Z",
        "id": "0a1a3f70-2f3c-5a1a-9b33-aaaaaaaaaaa5",
    },

    # South Prairie Elementary
    {
        "school_id": "b122fcb4-2864-593c-9b05-2188ef296db4",
        "name": "SP-101 Kindergarten Classroom",
        "capacity": 20,
        "created_at": "2024-01-01T11:00:00Z",
        "updated_at": "2024-01-01T11:00:00Z",
        "id": "0a1a3f70-2f3c-5a1a-9b33-bbbbbbbbbbb1",
    },
    {
        "school_id": "b122fcb4-2864-593c-9b05-2188ef296db4",
        "name": "SP-102 1st Grade Classroom",
        "capacity": 22,
        "created_at": "2024-01-01T12:00:00Z",
        "updated_at": "2024-01-01T12:00:00Z",
        "id": "0a1a3f70-2f3c-5a1a-9b33-bbbbbbbbbbb2",
    },
    {
        "school_id": "b122fcb4-2864-593c-9b05-2188ef296db4",
        "name": "SP-Resource Room",
        "capacity": 12,
        "created_at": "2024-01-01T13:00:00Z",
        "updated_at": "2024-01-01T13:00:00Z",
        "id": "0a1a3f70-2f3c-5a1a-9b33-bbbbbbbbbbb3",
    },
    {
        "school_id": "b122fcb4-2864-593c-9b05-2188ef296db4",
        "name": "SP-Gym",
        "capacity": 180,
        "created_at": "2024-01-01T14:00:00Z",
        "updated_at": "2024-01-01T14:00:00Z",
        "id": "0a1a3f70-2f3c-5a1a-9b33-bbbbbbbbbbb4",
    },
    {
        "school_id": "b122fcb4-2864-593c-9b05-2188ef296db4",
        "name": "SP-Music Room",
        "capacity": 40,
        "created_at": "2024-01-01T15:00:00Z",
        "updated_at": "2024-01-01T15:00:00Z",
        "id": "0a1a3f70-2f3c-5a1a-9b33-bbbbbbbbbbb5",
    },

    # Heritage Elementary
    {
        "school_id": "df4b1423-d755-5c7f-a0ba-6908de77f61b",
        "name": "HES-101 2nd Grade Classroom",
        "capacity": 22,
        "created_at": "2024-01-01T16:00:00Z",
        "updated_at": "2024-01-01T16:00:00Z",
        "id": "0a1a3f70-2f3c-5a1a-9b33-ccccccccccc1",
    },
    {
        "school_id": "df4b1423-d755-5c7f-a0ba-6908de77f61b",
        "name": "HES-102 3rd Grade Classroom",
        "capacity": 24,
        "created_at": "2024-01-01T17:00:00Z",
        "updated_at": "2024-01-01T17:00:00Z",
        "id": "0a1a3f70-2f3c-5a1a-9b33-ccccccccccc2",
    },
    {
        "school_id": "df4b1423-d755-5c7f-a0ba-6908de77f61b",
        "name": "HES-Resource Room",
        "capacity": 12,
        "created_at": "2024-01-01T18:00:00Z",
        "updated_at": "2024-01-01T18:00:00Z",
        "id": "0a1a3f70-2f3c-5a1a-9b33-ccccccccccc3",
    },
    {
        "school_id": "df4b1423-d755-5c7f-a0ba-6908de77f61b",
        "name": "HES-Gym",
        "capacity": 180,
        "created_at": "2024-01-01T19:00:00Z",
        "updated_at": "2024-01-01T19:00:00Z",
        "id": "0a1a3f70-2f3c-5a1a-9b33-ccccccccccc4",
    },
    {
        "school_id": "df4b1423-d755-5c7f-a0ba-6908de77f61b",
        "name": "HES-Art Room",
        "capacity": 30,
        "created_at": "2024-01-01T20:00:00Z",
        "updated_at": "2024-01-01T20:00:00Z",
        "id": "0a1a3f70-2f3c-5a1a-9b33-ccccccccccc5",
    },

    # North Ridge Elementary
    {
        "school_id": "634b8058-d620-5a5c-86b5-c0794d3a3b73",
        "name": "NRES-101 4th Grade Classroom",
        "capacity": 24,
        "created_at": "2024-01-01T21:00:00Z",
        "updated_at": "2024-01-01T21:00:00Z",
        "id": "0a1a3f70-2f3c-5a1a-9b33-ddddddddddd1",
    },
    {
        "school_id": "634b8058-d620-5a5c-86b5-c0794d3a3b73",
        "name": "NRES-102 5th Grade Classroom",
        "capacity": 24,
        "created_at": "2024-01-01T22:00:00Z",
        "updated_at": "2024-01-01T22:00:00Z",
        "id": "0a1a3f70-2f3c-5a1a-9b33-ddddddddddd2",
    },
    {
        "school_id": "634b8058-d620-5a5c-86b5-c0794d3a3b73",
        "name": "NRES-Resource Room",
        "capacity": 12,
        "created_at": "2024-01-01T23:00:00Z",
        "updated_at": "2024-01-01T23:00:00Z",
        "id": "0a1a3f70-2f3c-5a1a-9b33-ddddddddddd3",
    },
    {
        "school_id": "634b8058-d620-5a5c-86b5-c0794d3a3b73",
        "name": "NRES-Gym",
        "capacity": 160,
        "created_at": "2024-01-02T00:00:00Z",
        "updated_at": "2024-01-02T00:00:00Z",
        "id": "0a1a3f70-2f3c-5a1a-9b33-ddddddddddd4",
    },
    {
        "school_id": "634b8058-d620-5a5c-86b5-c0794d3a3b73",
        "name": "NRES-Library",
        "capacity": 45,
        "created_at": "2024-01-02T01:00:00Z",
        "updated_at": "2024-01-02T01:00:00Z",
        "id": "0a1a3f70-2f3c-5a1a-9b33-ddddddddddd5",
    },
]


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion from Python/inline values to appropriate DB values."""
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

    # Otherwise, pass raw through and let DB cast
    return raw


def upgrade() -> None:
    """Load seed data for rooms from inline SEED_ROWS."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(TABLE_NAME):
        log.warning("Table %s does not exist; skipping seed", TABLE_NAME)
        return

    metadata = sa.MetaData()
    table = sa.Table(TABLE_NAME, metadata, autoload_with=bind)

    if not SEED_ROWS:
        log.info("No inline seed rows defined for %s", TABLE_NAME)
        return

    inserted = 0
    for raw_row in SEED_ROWS:
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
                "Skipping inline row for %s due to error: %s. Row: %s",
                TABLE_NAME,
                exc,
                raw_row,
            )

    log.info("Inserted %s inline rows into %s", inserted, TABLE_NAME)


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
