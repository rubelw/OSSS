from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0098"
down_revision = "0097"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "announcements"


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion from Python value to something acceptable for the DB."""
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

    # Otherwise, pass raw through and let DB cast (for enums, timestamps, UUID, etc.)
    return raw


def upgrade() -> None:
    """Seed announcements with inline data.

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

    # Inline seed rows — aligned with Announcement model and your course/user data
    raw_rows = [
        {
            "user_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
            "course_id": "a4cddcde-b046-5dd4-8255-593ba99983c6",
            "text": (
                "Welcome to English III! Please review the course syllabus in Classroom "
                "and complete the introductory survey by Friday."
            ),
            "state": "PUBLISHED",
            "scheduled_time": "2024-08-19T13:00:00Z",
            "creation_time": "2024-08-18T15:30:00Z",
            "update_time": "2024-08-18T15:30:00Z",
            "id": "7a301a78-9162-5359-a608-30c583dc83db",
            "created_at": "2024-08-18T15:30:00Z",
            "updated_at": "2024-08-18T15:30:00Z",
        }
    ]

    if not raw_rows:
        log.info("No inline rows configured for %s", TABLE_NAME)
        return

    inserted = 0

    for raw_row in raw_rows:
        row: dict[str, object] = {}

        # Only include keys that actually exist as columns on this table
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

    log.info("Inserted %s inline rows into %s", inserted, TABLE_NAME)


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
