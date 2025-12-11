from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0107"
down_revision = "0106"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "student_guardians"

# Inline seed data; values are strings so the DB can cast
# to the correct types (UUID / TEXT / INTEGER / TIMESTAMPTZ, etc.).
INLINE_ROWS = [
    {
        "id": "4e5161e6-d3ae-5280-b6ca-f4f63a6d3fe4",
        "student_id": "d4f53e78-1012-5322-a4f3-4bca2efc51be",
        "guardian_id": "ba756e0b-7456-5d58-bac4-e6afdd286c3d",
        "custody": "student_guardians_custody_1",
        "is_primary": "student_guardians_is_primary_1",
        "contact_order": "1",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
    },
    {
        "id": "68428b26-5a46-5367-a953-6a9b091451a8",
        "student_id": "d4f53e78-1012-5322-a4f3-4bca2efc51be",
        "guardian_id": "ba756e0b-7456-5d58-bac4-e6afdd286c3d",
        "custody": "student_guardians_custody_2",
        "is_primary": "student_guardians_is_primary_2",
        "contact_order": "2",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
    },
    {
        "id": "a0934989-a686-5bdd-9436-f08cefa5ee35",
        "student_id": "d4f53e78-1012-5322-a4f3-4bca2efc51be",
        "guardian_id": "ba756e0b-7456-5d58-bac4-e6afdd286c3d",
        "custody": "student_guardians_custody_3",
        "is_primary": "student_guardians_is_primary_3",
        "contact_order": "3",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
    },
    {
        "id": "bf07b024-836f-5d91-82a4-66decc94466e",
        "student_id": "d4f53e78-1012-5322-a4f3-4bca2efc51be",
        "guardian_id": "ba756e0b-7456-5d58-bac4-e6afdd286c3d",
        "custody": "student_guardians_custody_4",
        "is_primary": "student_guardians_is_primary_4",
        "contact_order": "4",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
    },
    {
        "id": "1497aeee-c229-52f4-943c-3af3da70c59a",
        "student_id": "d4f53e78-1012-5322-a4f3-4bca2efc51be",
        "guardian_id": "ba756e0b-7456-5d58-bac4-e6afdd286c3d",
        "custody": "student_guardians_custody_5",
        "is_primary": "student_guardians_is_primary_5",
        "contact_order": "5",
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

    # Otherwise, pass raw through and let DB cast (UUID, TEXT, INTEGER, TIMESTAMPTZ, etc.)
    return raw


def upgrade() -> None:
    """Load seed data for student_guardians from inline rows.

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
