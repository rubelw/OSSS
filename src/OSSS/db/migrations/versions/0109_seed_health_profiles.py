from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0109"
down_revision = "0108"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "health_profiles"

# Inline seed data; values are strings so the DB can cast
# to the correct types (UUID / TEXT / TIMESTAMPTZ, etc.).
INLINE_ROWS = [
    {
        "student_id": "d4f53e78-1012-5322-a4f3-4bca2efc51be",
        "allergies": "health_profiles_allergies_1",
        "conditions": "health_profiles_conditions_1",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
        "id": "7a856310-75c2-5c13-be44-07370699ddbc",
    },
    {
        "student_id": "d4f53e78-1012-5322-a4f3-4bca2efc51be",
        "allergies": "health_profiles_allergies_2",
        "conditions": "health_profiles_conditions_2",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
        "id": "6001c8ae-ede3-55c1-89c0-38897a73d8a2",
    },
    {
        "student_id": "d4f53e78-1012-5322-a4f3-4bca2efc51be",
        "allergies": "health_profiles_allergies_3",
        "conditions": "health_profiles_conditions_3",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
        "id": "4f9d0c7d-2f83-53b4-bb9c-c79ebc4a6931",
    },
    {
        "student_id": "d4f53e78-1012-5322-a4f3-4bca2efc51be",
        "allergies": "health_profiles_allergies_4",
        "conditions": "health_profiles_conditions_4",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
        "id": "2affc31e-552d-5a8a-886b-06fa6ee1bd86",
    },
    {
        "student_id": "d4f53e78-1012-5322-a4f3-4bca2efc51be",
        "allergies": "health_profiles_allergies_5",
        "conditions": "health_profiles_conditions_5",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
        "id": "828368fd-939e-5c42-b2b9-477b6d579600",
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

    # Otherwise, pass raw through and let DB cast (UUID, TEXT, TIMESTAMPTZ, etc.)
    return raw


def upgrade() -> None:
    """Load seed data for health_profiles from inline rows.

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
        row: dict[str, object] = {}

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
