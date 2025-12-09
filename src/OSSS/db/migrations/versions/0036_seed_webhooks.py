from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0036"
down_revision = "0035"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "webhooks"

# Inline seed data aligned to Webhook model:
#   - target_url <- url
#   - events     <- [event_type]
#   - secret     <- None
SEED_ROWS = [
    {
        "id": "ce9e3701-7ec0-4326-9b38-5136c9450b0a",
        "target_url": "https://hooks.example.com/student_created",
        "secret": None,
        "events": ["student.created"],
    },
    {
        "id": "d7f0dee9-c07f-4601-9241-2931d1adb7ec",
        "target_url": "https://hooks.example.com/student_updated",
        "secret": None,
        "events": ["student.updated"],
    },
    {
        "id": "1b4512fd-bf12-4a20-9ade-36a5452d9250",
        "target_url": "https://hooks.example.com/attendance_posted",
        "secret": None,
        "events": ["attendance.posted"],
    },
    {
        "id": "8170ae1c-4d8a-456d-8cbc-54f4e3d12d4d",
        "target_url": "https://hooks.example.com/grade_finalized",
        "secret": None,
        "events": ["grade.finalized"],
    },
    {
        "id": "8932b45a-537d-4673-9baa-b37b2a143863",
        "target_url": "https://hooks.example.com/ticket_scanned",
        "secret": None,
        "events": ["ticket.scanned"],
        # note: original is_active=false is not represented in the model,
        # so it is ignored here.
    },
]


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion from inline value to appropriate DB-bound value."""
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

    # For JSONB, lists/dicts are fine; driver will handle them.
    # Otherwise, pass raw through and let DB cast.
    return raw


def upgrade() -> None:
    """Load seed data for webhooks from inline SEED_ROWS.

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
