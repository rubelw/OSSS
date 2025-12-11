from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0105"
down_revision = "0104"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "assignments"

# Inline seed data; values are strings so the DB can cast
# to the correct types (UUID / DATE / NUMERIC / TIMESTAMPTZ, etc.).
INLINE_ROWS = [
    {
        "section_id": "6e9f574f-c3ac-505d-baee-e525351b2788",
        "category_id": "b4a627d0-7477-55a9-92d2-4bc6f86ea89f",
        "name": "assignments_name_1",
        "due_date": "2024-01-02",
        "points_possible": "1",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
        "id": "0e5a804a-8bcd-5711-8e93-1fa2cc7bf006",
    },
    {
        "section_id": "6e9f574f-c3ac-505d-baee-e525351b2788",
        "category_id": "b4a627d0-7477-55a9-92d2-4bc6f86ea89f",
        "name": "assignments_name_2",
        "due_date": "2024-01-03",
        "points_possible": "2",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
        "id": "9328284e-7fc6-5dfd-8c3e-2abd66e70172",
    },
    {
        "section_id": "6e9f574f-c3ac-505d-baee-e525351b2788",
        "category_id": "b4a627d0-7477-55a9-92d2-4bc6f86ea89f",
        "name": "assignments_name_3",
        "due_date": "2024-01-04",
        "points_possible": "3",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
        "id": "3b3377b8-7194-5f5d-97d5-7190735f46bd",
    },
    {
        "section_id": "6e9f574f-c3ac-505d-baee-e525351b2788",
        "category_id": "b4a627d0-7477-55a9-92d2-4bc6f86ea89f",
        "name": "assignments_name_4",
        "due_date": "2024-01-05",
        "points_possible": "4",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
        "id": "ad916c34-1f6a-5ebd-9345-48aeca114d37",
    },
    {
        "section_id": "6e9f574f-c3ac-505d-baee-e525351b2788",
        "category_id": "b4a627d0-7477-55a9-92d2-4bc6f86ea89f",
        "name": "assignments_name_5",
        "due_date": "2024-01-06",
        "points_possible": "5",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
        "id": "1e3bfda9-a9c0-5be8-a0a0-fdda9fc15a1e",
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
            log.warning(
                "Invalid boolean for %s.%s: %r; using NULL",
                TABLE_NAME,
                col.name,
                raw,
            )
            return None
        return bool(raw)

    # Otherwise, pass raw through and let DB cast (UUID, DATE, NUMERIC, TIMESTAMPTZ, etc.)
    return raw


def upgrade() -> None:
    """Load seed data for assignments from inline rows.

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

    log.info(
        "Inserted %s rows into %s from inline seed data",
        inserted,
        TABLE_NAME,
    )


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
