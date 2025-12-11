from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0118"
down_revision = "0117"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "evaluation_assignments"

# Inline seed data
ROWS = [
    {
        "cycle_id": "5997aacd-a6e7-500a-add0-ef0b4a81700e",
        "subject_user_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "evaluator_user_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "template_id": "f48b66b5-fbda-4b6f-9d40-048fdd6839de",
        "status": "evaluation_assignments_status_1",
        "id": "a5d5a408-430c-57f7-941a-9bd0d8ed9049",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
    },
    {
        "cycle_id": "5997aacd-a6e7-500a-add0-ef0b4a81700e",
        "subject_user_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "evaluator_user_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "template_id": "f48b66b5-fbda-4b6f-9d40-048fdd6839de",
        "status": "evaluation_assignments_status_2",
        "id": "ba9a36c3-41d5-57bb-84e0-25b5d8adc0ea",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
    },
    {
        "cycle_id": "5997aacd-a6e7-500a-add0-ef0b4a81700e",
        "subject_user_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "evaluator_user_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "template_id": "f48b66b5-fbda-4b6f-9d40-048fdd6839de",
        "status": "evaluation_assignments_status_3",
        "id": "5d2f8500-6ee9-57f3-9218-83676ab43da6",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
    },
    {
        "cycle_id": "5997aacd-a6e7-500a-add0-ef0b4a81700e",
        "subject_user_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "evaluator_user_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "template_id": "f48b66b5-fbda-4b6f-9d40-048fdd6839de",
        "status": "evaluation_assignments_status_4",
        "id": "83bca01a-69b9-5771-8795-044b23b6fd0b",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
    },
    {
        "cycle_id": "5997aacd-a6e7-500a-add0-ef0b4a81700e",
        "subject_user_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "evaluator_user_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "template_id": "f48b66b5-fbda-4b6f-9d40-048fdd6839de",
        "status": "evaluation_assignments_status_5",
        "id": "9bbf3cad-9a87-5dd7-9e33-98c38aa3ea56",
        "created_at": "2024-01-01T05:00:00Z",
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

    # Let the DB cast for GUID, Integer, Timestamptz, etc.
    return raw


def upgrade() -> None:
    """Seed fixed evaluation_assignments rows inline.

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

    inserted = 0
    for raw_row in ROWS:
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

    log.info("Inserted %s rows into %s (inline seed)", inserted, TABLE_NAME)


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
