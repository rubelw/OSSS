from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0054"
down_revision = "0053"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "activities"


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion from Python/inline value to appropriate DB value."""
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
    """Seed the activities table with inline data.

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

    # Inline seed rows
    rows = [
        {
            "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
            "name": "DCG High School Student Council",
            "description": (
                "Student leadership organization that plans school-wide events and "
                "represents the student body in collaboration with administration"
            ),
            "is_active": True,
            "created_at": "2024-01-01T01:00:00Z",
            "updated_at": "2024-01-01T01:00:00Z",
            "id": "e6626448-82fb-56c2-915e-166743fd5841",
        },
        {
            "school_id": "119caaef-ef97-5364-b179-388e108bd40d",
            "name": "DCG Middle School Show Choir",
            "description": (
                "Vocal music ensemble that rehearses and performs choreographed choral "
                "music at school and community events"
            ),
            "is_active": True,
            "created_at": "2024-01-01T02:00:00Z",
            "updated_at": "2024-01-01T02:00:00Z",
            "id": "3d3be493-df36-5c4d-a38c-b2234a0848ce",
        },
        {
            "school_id": "b122fcb4-2864-593c-9b05-2188ef296db4",
            "name": "South Prairie Running Club",
            "description": (
                "Elementary after-school running and wellness club that prepares "
                "students for local fun runs and promotes healthy habits"
            ),
            "is_active": False,
            "created_at": "2024-01-01T03:00:00Z",
            "updated_at": "2024-01-01T03:00:00Z",
            "id": "03d9bb2e-6006-59da-bd69-bcc9dea7a57d",
        },
        {
            "school_id": "df4b1423-d755-5c7f-a0ba-6908de77f61b",
            "name": "Heritage LEGO Robotics Club",
            "description": (
                "Hands-on STEM club where students design, build, and program "
                "LEGO-based robots for simple challenges and showcases"
            ),
            "is_active": True,
            "created_at": "2024-01-01T04:00:00Z",
            "updated_at": "2024-01-01T04:00:00Z",
            "id": "b9fc62b7-4c3d-57f3-ac8b-f4cb764ab76d",
        },
        {
            "school_id": "634b8058-d620-5a5c-86b5-c0794d3a3b73",
            "name": "North Ridge After-School Art Club",
            "description": (
                "Creative arts club offering drawing, painting, and mixed-media "
                "projects beyond the regular elementary art curriculum"
            ),
            "is_active": False,
            "created_at": "2024-01-01T05:00:00Z",
            "updated_at": "2024-01-01T05:00:00Z",
            "id": "9fe2a3e0-ebe9-5333-aa24-53cd7df52e7d",
        },
    ]

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

    log.info("Inserted %s rows into %s (inline seed)", inserted, TABLE_NAME)


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
