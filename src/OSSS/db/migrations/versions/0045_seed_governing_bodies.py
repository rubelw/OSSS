from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0045"
down_revision = "0044"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "governing_bodies"

# Inline seed data aligned with GoverningBody model
SEED_ROWS = [
    {
        "org_id": "c201e5e9-60c0-466f-8f63-aecbf868c420",
        "name": "Dallas Center-Grimes CSD Board of Education",
        "type": "board_of_education",
        "id": "4b9ddc27-7c2b-4b4b-8c9b-4d2f3f4c1234",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
    },
    {
        "org_id": "495c02aa-3e2e-4d4e-9623-7880d523bf71",
        "name": "Grimes Parks & Rec Advisory Board",
        "type": "advisory_board",
        "id": "9c8f0c3e-9a39-4a8a-93d4-3a0a2f6a5678",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
    },
    {
        "org_id": "243e4944-068c-44f0-aa26-4ba25ff9339a",
        "name": "DCG Education Foundation Board",
        "type": "nonprofit_board",
        "id": "1f37e3b0-2e4b-4e1d-9f3f-1a2b3c4d9abc",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
    },
    {
        "org_id": "27ecfe2b-fe0d-4522-aa8a-ed65fd5f4419",
        "name": "Booster Club Executive Board",
        "type": "booster_board",
        "id": "7e5a1a8c-3b21-4c4a-8b0e-5f6e7a8b0def",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
    },
    {
        "org_id": "a2e9b7f7-6fc8-48c4-950e-2300dc3f02fc",
        "name": "Local PTO Council",
        "type": "pto_council",
        "id": "d3abf2e1-6a9c-4f77-9b4a-2c5d6e7f0123",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
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
            log.warning("Invalid boolean for %s.%s: %r; using NULL", TABLE_NAME, col.name, raw)
            return None
        return bool(raw)

    # Otherwise, pass raw through and let DB cast (dates, enums, etc.)
    return raw


def upgrade() -> None:
    """Load seed data for governing_bodies from inline SEED_ROWS.

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
                # Let TimestampMixin defaults handle created_at/updated_at if not provided
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
