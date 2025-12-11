from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0089"
down_revision = "0088"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "evaluation_cycles"


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion from CSV/inline string to appropriate Python value."""
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
    """Seed evaluation_cycles with inline data.

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

    # Inline seed data (instead of reading from CSV)
    rows = [
        {
            "org_id": "c201e5e9-60c0-466f-8f63-aecbf868c420",
            "name": "Teacher Comprehensive Evaluation (2024–2025)",
            "start_at": "2024-08-23T00:00:00Z",
            "end_at": "2025-05-23T23:59:59Z",
            "id": "5997aacd-a6e7-500a-add0-ef0b4a81700e",
            "created_at": "2024-01-01T01:00:00Z",
            "updated_at": "2024-01-01T01:00:00Z",
        },
        {
            "org_id": "c201e5e9-60c0-466f-8f63-aecbf868c420",
            "name": "Teacher Focused/Annual Evaluation (2024–2025)",
            "start_at": "2024-08-23T00:00:00Z",
            "end_at": "2025-05-23T23:59:59Z",
            "id": "9642d929-b043-500e-8d78-281a0e895f54",
            "created_at": "2024-01-01T02:00:00Z",
            "updated_at": "2024-01-01T02:00:00Z",
        },
        {
            "org_id": "c201e5e9-60c0-466f-8f63-aecbf868c420",
            "name": "New Teacher Induction & Evaluation (2024–2025)",
            "start_at": "2024-08-01T00:00:00Z",
            "end_at": "2025-05-31T23:59:59Z",
            "id": "ef607a19-18a2-5086-8a8b-348b4c021e6a",
            "created_at": "2024-01-01T03:00:00Z",
            "updated_at": "2024-01-01T03:00:00Z",
        },
        {
            "org_id": "c201e5e9-60c0-466f-8f63-aecbf868c420",
            "name": "Administrator Annual Evaluation (2024–2025)",
            "start_at": "2024-07-01T00:00:00Z",
            "end_at": "2025-06-30T23:59:59Z",
            "id": "b051e2a7-17b8-593a-93de-dc862b9145ca",
            "created_at": "2024-01-01T04:00:00Z",
            "updated_at": "2024-01-01T04:00:00Z",
        },
        {
            "org_id": "c201e5e9-60c0-466f-8f63-aecbf868c420",
            "name": "Classified Staff Performance Review Cycle (2024–2025)",
            "start_at": "2024-07-01T00:00:00Z",
            "end_at": "2025-06-30T23:59:59Z",
            "id": "f9ecfede-bc18-50a1-b98b-cb5b4234be32",
            "created_at": "2024-01-01T05:00:00Z",
            "updated_at": "2024-01-01T05:00:00Z",
        },
    ]

    if not rows:
        log.info("No inline rows defined for %s", TABLE_NAME)
        return

    inserted = 0
    for raw_row in rows:
        row: dict[str, Any] = {}

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

    log.info("Inserted %s inline rows into %s", inserted, TABLE_NAME)


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
