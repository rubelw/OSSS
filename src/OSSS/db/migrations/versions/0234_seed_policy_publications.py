from __future__ import annotations

import logging
from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0234"
down_revision = "0233"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "policy_publications"

# ---------------------------------------------------------------------------
# Inline realistic seed data
# Columns: policy_version_id, published_at, public_url, is_current
#
# Realistic scenario:
#  - Policy version published in 2024 after review.
#  - Only the most recent publication is current.
# ---------------------------------------------------------------------------

SEED_ROWS = [
    {
        "policy_version_id": "220ea1db-70a4-506f-8039-ffe4637cea69",
        "published_at": "2024-01-01T03:00:00Z",
        "public_url": "https://district.example.org/policies/2024/update-1",
        "is_current": False,
    },

]


def _coerce_value(col: sa.Column, raw):
    """Coerce inline row values to correct types."""
    if raw == "" or raw is None:
        return None

    t = col.type

    # Boolean normalization
    if isinstance(t, sa.Boolean):
        if isinstance(raw, str):
            v = raw.lower().strip()
            if v in ("true", "1", "yes", "y"):
                return True
            if v in ("false", "0", "no", "n"):
                return False
            log.warning("Invalid boolean for %s.%s: %r", TABLE_NAME, col.name, raw)
            return None
        return bool(raw)

    # Allow database to cast UUID, timestamp, etc.
    return raw


def upgrade() -> None:
    """Insert inline seed rows into policy_publications."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(TABLE_NAME):
        log.warning("Table %s does not exist; skipping.", TABLE_NAME)
        return

    metadata = sa.MetaData()
    table = sa.Table(TABLE_NAME, metadata, autoload_with=bind)

    inserted = 0

    for raw_row in SEED_ROWS:
        row = {}

        for col in table.columns:
            if col.name not in raw_row:
                continue

            val = _coerce_value(col, raw_row[col.name])
            row[col.name] = val

        nested = bind.begin_nested()
        try:
            bind.execute(table.insert().values(**row))
            nested.commit()
            inserted += 1
        except (IntegrityError, DataError, StatementError) as exc:
            nested.rollback()
            log.warning("Skipping row for %s due to error: %s | Row: %s", TABLE_NAME, exc, raw_row)

    log.info("Inserted %s inline rows into %s", inserted, TABLE_NAME)


def downgrade() -> None:
    # Seed data remains in place
    pass
