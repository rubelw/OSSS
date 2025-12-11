from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0077"
down_revision = "0076"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "guardians"

# Inline seed rows
SEED_ROWS = [
    {
        "student_user_id": "bf98bfb1-547f-5bd5-9c70-2b789e0bfb4b",
        "guardian_user_id": "bf98bfb1-547f-5bd5-9c70-2b789e0bfb4b",
        "guardian_email": "michael.smith.parent@example.com",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
        "id": "ba756e0b-7456-5d58-bac4-e6afdd286c3d",
    }
]


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion from Python/inline values to appropriate DB values."""
    if raw == "" or raw is None:
        return None

    t = col.type

    # Boolean handling (not used here but kept for consistency with other seeds)
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

    # Let the DB cast UUID/timestamps/strings
    return raw


def upgrade() -> None:
    """Load seed data for guardians from inline SEED_ROWS."""

    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(TABLE_NAME):
        log.warning("Table %s does not exist; skipping seed", TABLE_NAME)
        return

    metadata = sa.MetaData()
    table = sa.Table(TABLE_NAME, metadata, autoload_with=bind)

    if not SEED_ROWS:
        log.info("No inline seed rows defined for %s; skipping", TABLE_NAME)
        return

    inserted = 0
    for raw_row in SEED_ROWS:
        row = {}

        # Only include columns that actually exist on the table
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
                "Skipping inline row for %s due to error: %s. Row: %s",
                TABLE_NAME,
                exc,
                raw_row,
            )

    log.info("Inserted %s inline rows into %s", inserted, TABLE_NAME)


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
