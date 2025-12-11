from __future__ import annotations

import logging
from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0095"
down_revision = "0094"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "floors"

# ---------------------------------------------------------------------------
# Inline seed data (replaces CSV)
# ---------------------------------------------------------------------------
SEED_ROWS = [
    {
        "building_id": "2fcc53b4-7367-5852-9afb-ffdecafad618",
        "level_code": "MS01",
        "name": "main_floor",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
        "id": "f8e212b7-a5fe-5f06-994e-d21dce9f765f",
    }
]


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion from Python values into SQLAlchemy-consumable values."""
    if raw == "" or raw is None:
        return None

    t = col.type

    # Boolean coercion if ever needed
    if isinstance(t, sa.Boolean):
        if isinstance(raw, str):
            v = raw.strip().lower()
            if v in ("true", "t", "1", "yes", "y"):
                return True
            if v in ("false", "f", "0", "no", "n"):
                return False
            log.warning(
                "Invalid boolean for %s.%s: %r; using NULL",
                TABLE_NAME, col.name, raw
            )
            return None
        return bool(raw)

    return raw


def upgrade() -> None:
    """Load inline seed data for `floors`."""

    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(TABLE_NAME):
        log.warning("Table %s does not exist; skipping seed", TABLE_NAME)
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
            row[col.name] = _coerce_value(col, raw_val)

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
                "Skipping row for %s due to error: %s | Row: %s",
                TABLE_NAME, exc, raw_row
            )

    log.info("Inserted %s rows into %s from inline seed", inserted, TABLE_NAME)


def downgrade() -> None:
    # No-op: leave seed data in place
    pass
