from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0206"
down_revision = "0205"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "sessions"

# Inline seed rows with realistic data
# Columns: student_id, subject, objective_code, created_at, id, updated_at
SEED_ROWS = [
    {
        "student_id": "d4f53e78-1012-5322-a4f3-4bca2efc51be",
        "subject": "Mathematics – Fractions Review",
        "objective_code": "MATH-5.NF.1",
        "created_at": "2024-01-01T01:00:00Z",
        "id": "28da96d8-0d7c-5def-afa2-7c2996853fb2",
        "updated_at": "2024-01-01T01:00:00Z",
    },
    {
        "student_id": "d4f53e78-1012-5322-a4f3-4bca2efc51be",
        "subject": "English Language Arts – Reading Comprehension",
        "objective_code": "ELA-5.RI.2",
        "created_at": "2024-01-01T02:00:00Z",
        "id": "b7f03589-8670-5810-809c-5c8bc84688cb",
        "updated_at": "2024-01-01T02:00:00Z",
    },
    {
        "student_id": "d4f53e78-1012-5322-a4f3-4bca2efc51be",
        "subject": "Science – Weather and Climate",
        "objective_code": "SCI-5.ESS2.A",
        "created_at": "2024-01-01T03:00:00Z",
        "id": "196f2b90-e1e1-5676-b203-9f8b431bb9fd",
        "updated_at": "2024-01-01T03:00:00Z",
    },
    {
        "student_id": "d4f53e78-1012-5322-a4f3-4bca2efc51be",
        "subject": "Social Studies – Early American History",
        "objective_code": "SS-5.H.3",
        "created_at": "2024-01-01T04:00:00Z",
        "id": "c1489910-56b3-5e9e-9e61-f7afa208fca5",
        "updated_at": "2024-01-01T04:00:00Z",
    },
    {
        "student_id": "d4f53e78-1012-5322-a4f3-4bca2efc51be",
        "subject": "Mathematics – Multi-Digit Multiplication Practice",
        "objective_code": "MATH-5.NBT.B.5",
        "created_at": "2024-01-01T05:00:00Z",
        "id": "fee879db-c580-5ebc-b749-f4881788adc9",
        "updated_at": "2024-01-01T05:00:00Z",
    },
]


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion from inline values to appropriate Python/DB values."""
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
    """Load seed data for sessions from inline SEED_ROWS.

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

    rows = SEED_ROWS
    if not rows:
        log.info("No inline seed rows defined for %s", TABLE_NAME)
        return

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

    log.info("Inserted %s inline seed rows into %s", inserted, TABLE_NAME)


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
