from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0106"
down_revision = "0105"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "grade_scale_bands"

# Inline seed data; values are strings so the DB can cast
# to the correct types (UUID / NUMERIC / TIMESTAMPTZ, etc.).
INLINE_ROWS = [
    {
        "grade_scale_id": "5f19c7c0-5715-5f26-86bc-2b752469dd29",
        "label": "grade_scale_bands_label_1",
        "min_value": "1",
        "max_value": "1",
        "gpa_points": "1",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
        "id": "2ac2dcfe-af0d-5b3d-bfaf-f49401457d0e",
    },
    {
        "grade_scale_id": "5f19c7c0-5715-5f26-86bc-2b752469dd29",
        "label": "grade_scale_bands_label_2",
        "min_value": "2",
        "max_value": "2",
        "gpa_points": "2",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
        "id": "8f361858-9b42-5440-870d-f59f3de00775",
    },
    {
        "grade_scale_id": "5f19c7c0-5715-5f26-86bc-2b752469dd29",
        "label": "grade_scale_bands_label_3",
        "min_value": "3",
        "max_value": "3",
        "gpa_points": "3",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
        "id": "8a5a464e-088b-5043-9ff3-6060ed00cd5d",
    },
    {
        "grade_scale_id": "5f19c7c0-5715-5f26-86bc-2b752469dd29",
        "label": "grade_scale_bands_label_4",
        "min_value": "4",
        "max_value": "4",
        "gpa_points": "4",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
        "id": "508903ed-5896-57f4-9168-4eee42220566",
    },
    {
        "grade_scale_id": "5f19c7c0-5715-5f26-86bc-2b752469dd29",
        "label": "grade_scale_bands_label_5",
        "min_value": "5",
        "max_value": "5",
        "gpa_points": "5",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
        "id": "5c7f6171-7d97-52ad-8cdf-1cc94bfd4c09",
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

    # Otherwise, pass raw through and let DB cast (UUID, NUMERIC, TIMESTAMPTZ, etc.)
    return raw


def upgrade() -> None:
    """Load seed data for grade_scale_bands from inline rows.

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
