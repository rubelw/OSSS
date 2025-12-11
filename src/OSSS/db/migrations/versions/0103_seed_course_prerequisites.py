from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0103"
down_revision = "0102"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "course_prerequisites"

# Inline seed data; values are strings so the DB can cast
# to the correct types (UUID / TIMESTAMPTZ, etc.).
INLINE_ROWS = [
    {
        "id": "6d07a61e-20f7-53ef-b0d1-a409d731e023",
        "course_id": "a4cddcde-b046-5dd4-8255-593ba99983c6",
        "prereq_course_id": "a4cddcde-b046-5dd4-8255-593ba99983c6",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
    },
    {
        "id": "64741053-7f89-53f8-977e-1adf1facd2ac",
        "course_id": "a4cddcde-b046-5dd4-8255-593ba99983c6",
        "prereq_course_id": "a4cddcde-b046-5dd4-8255-593ba99983c6",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
    },
    {
        "id": "746c85b6-6e26-5d4d-84b8-3718c99721bf",
        "course_id": "a4cddcde-b046-5dd4-8255-593ba99983c6",
        "prereq_course_id": "a4cddcde-b046-5dd4-8255-593ba99983c6",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
    },
    {
        "id": "cf3122a5-1616-5fd5-bf4d-fe071c5b7141",
        "course_id": "a4cddcde-b046-5dd4-8255-593ba99983c6",
        "prereq_course_id": "a4cddcde-b046-5dd4-8255-593ba99983c6",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
    },
    {
        "id": "c8259287-d068-5f1c-a1bc-d23cc92a3248",
        "course_id": "a4cddcde-b046-5dd4-8255-593ba99983c6",
        "prereq_course_id": "a4cddcde-b046-5dd4-8255-593ba99983c6",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
    },
]


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion from inline seed data to appropriate Python value."""
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
            log.warning("Invalid boolean for %s.%s: %r; using NULL", TABLE_NAME, col.name, raw)
            return None
        return bool(raw)

    # Otherwise, pass raw through and let DB cast (UUID, TIMESTAMPTZ, etc.)
    return raw


def upgrade() -> None:
    """Load seed data for course_prerequisites from inline rows.

    Each row is inserted inside an explicit nested transaction (SAVEPOINT)
    so a failing row won't abort the whole migration transaction.
    """
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(TABLE_NAME):
        log.warning("Table %s does not exist; skipping seed", TABLE_NAME)
        return

    if not INLINE_ROWS:
        log.info("No inline rows defined for %s; nothing to insert", TABLE_NAME)
        return

    metadata = sa.MetaData()
    table = sa.Table(TABLE_NAME, metadata, autoload_with=bind)

    inserted = 0
    for raw_row in INLINE_ROWS:
        row = {}

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

    log.info("Inserted %s rows into %s from inline seed data", inserted, TABLE_NAME)


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
