from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0104"
down_revision = "0103"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "assignment_categories"

# Inline seed data; values are strings so the DB can cast
# to the correct types (UUID / NUMERIC / TIMESTAMPTZ, etc.).
INLINE_ROWS = [
    {
        "section_id": "6e9f574f-c3ac-505d-baee-e525351b2788",
        "name": "assignment_categories_name_1",
        "weight": "1",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
        "id": "b4a627d0-7477-55a9-92d2-4bc6f86ea89f",
    },
    {
        "section_id": "6e9f574f-c3ac-505d-baee-e525351b2788",
        "name": "assignment_categories_name_2",
        "weight": "2",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
        "id": "28fb37a8-948a-5d48-ba5e-640d00839c39",
    },
    {
        "section_id": "6e9f574f-c3ac-505d-baee-e525351b2788",
        "name": "assignment_categories_name_3",
        "weight": "3",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
        "id": "84b069e9-fd98-502b-b75d-3f2af8eca98c",
    },
    {
        "section_id": "6e9f574f-c3ac-505d-baee-e525351b2788",
        "name": "assignment_categories_name_4",
        "weight": "4",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
        "id": "2866959e-e188-5ee9-809a-ab913a26ffd8",
    },
    {
        "section_id": "6e9f574f-c3ac-505d-baee-e525351b2788",
        "name": "assignment_categories_name_5",
        "weight": "5",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
        "id": "79399d8a-32d4-5071-9506-4d9653b6c3c9",
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

    # Otherwise, pass raw through and let DB cast (UUID, NUMERIC, TIMESTAMPTZ, etc.)
    return raw


def upgrade() -> None:
    """Load seed data for assignment_categories from inline rows.

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
