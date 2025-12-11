from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0117"
down_revision = "0116"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "evaluation_sections"

# Inline seed data
ROWS = [
    {
        "template_id": "f48b66b5-fbda-4b6f-9d40-048fdd6839de",
        "title": "evaluation_sections_title_1",
        "order_no": "1",
        "id": "7086aafb-4277-5f98-91c2-bd55e42e5149",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
    },
    {
        "template_id": "f48b66b5-fbda-4b6f-9d40-048fdd6839de",
        "title": "evaluation_sections_title_2",
        "order_no": "2",
        "id": "85b73578-2be1-5bc8-92d8-1a039e2209e9",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
    },
    {
        "template_id": "f48b66b5-fbda-4b6f-9d40-048fdd6839de",
        "title": "evaluation_sections_title_3",
        "order_no": "3",
        "id": "b0ba4043-6107-5a59-8db9-2119134bd881",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
    },
    {
        "template_id": "f48b66b5-fbda-4b6f-9d40-048fdd6839de",
        "title": "evaluation_sections_title_4",
        "order_no": "4",
        "id": "0d1355de-f9e4-58e3-b537-63f8aa87303b",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
    },
    {
        "template_id": "f48b66b5-fbda-4b6f-9d40-048fdd6839de",
        "title": "evaluation_sections_title_5",
        "order_no": "5",
        "id": "0218c0bb-698d-5c36-b4e3-930a0df728d6",
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

    # Let the DB cast for Integer/UUID/Timestamptz/etc.
    return raw


def upgrade() -> None:
    """Seed fixed evaluation_sections rows inline.

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
