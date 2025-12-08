from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "standardized_tests"

SEED_ROWS = [
    {
        "id": "e13c8240-a3ee-423b-8102-ab9fbceead13",
        "name": "Iowa State Assessment",
        "subject": "Composite",
        "grade_levels": "3-11",
        "state": "IA",
    },
    {
        "id": "17c3a1b0-dbfe-443a-8c21-eb0dff5c4a78",
        "name": "MAP Reading",
        "subject": "Reading",
        "grade_levels": "3-11",
        "state": "IA",
    },
    {
        "id": "4f544827-2d47-4cc8-a9cd-e1e0dfd03c5d",
        "name": "MAP Math",
        "subject": "Math",
        "grade_levels": "3-11",
        "state": "IA",
    },
    {
        "id": "21f8ee4a-4027-4deb-8157-9c83aaeea2db",
        "name": "ACT",
        "subject": "Composite",
        "grade_levels": "3-11",
        "state": "IA",
    },
    {
        "id": "51f53716-f4d6-40ec-877d-b1c41594e9e6",
        "name": "PSAT",
        "subject": "Composite",
        "grade_levels": "3-11",
        "state": "IA",
    },
]


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion from Python/CSV-style value to appropriate DB value."""
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
    """Load seed data for standardized_tests from inline SEED_ROWS.

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
