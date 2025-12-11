from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0102"
down_revision = "0101"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "course_teachers"

# Inline seed data; values are strings so the DB can cast
# to the correct types (UUID / INT / TIMESTAMP, etc.).
INLINE_ROWS = [
    {
        "course_id": "a4cddcde-b046-5dd4-8255-593ba99983c6",
        "user_id": "bf98bfb1-547f-5bd5-9c70-2b789e0bfb4b",
        "id": "215c2b34-51aa-5518-8cea-93d7cbafb146",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
    },
    {
        "course_id": "a4cddcde-b046-5dd4-8255-593ba99983c6",
        "user_id": "c16445fe-670c-5225-91b8-765ae3b7fec2",
        "id": "f9159e04-4f91-5039-b1f3-49613f3544dd",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
    },
    {
        "course_id": "a4cddcde-b046-5dd4-8255-593ba99983c6",
        "user_id": "27e38c8d-d0f3-550d-8c7a-614e63d960d3",
        "id": "520a9e21-ee36-5987-bbca-d981b0730f53",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
    },
    {
        "course_id": "a4cddcde-b046-5dd4-8255-593ba99983c6",
        "user_id": "692dfafb-bcfa-560e-84d8-be00ce5d1b97",
        "id": "974feb00-cd0b-5272-9641-86cd778766cd",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
    },
    {
        "course_id": "a4cddcde-b046-5dd4-8255-593ba99983c6",
        "user_id": "8759b06a-0165-5e63-96b9-07682bf2ad11",
        "id": "4c62807e-b9cc-52e5-b0f8-daa1abf87470",
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

    # Otherwise, pass raw through and let DB cast
    return raw


def upgrade() -> None:
    """Load seed data for course_teachers from inline rows.

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
