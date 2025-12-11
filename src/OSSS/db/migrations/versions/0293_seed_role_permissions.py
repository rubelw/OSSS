from __future__ import annotations

import csv
import logging
import os
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0293"
down_revision = "0292"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "role_permissions"
CSV_FILE = os.path.join(os.path.dirname(__file__), "csv", f"{TABLE_NAME}.csv")

# Inline seed data (id, role_id, permission_id, created_at, updated_at)
SEED_ROWS = [
    {
        "id": "2040bb2c-bafb-5bd7-88dd-8c1bf09e926c",
        "role_id": "f544f901-921e-471f-a62a-06bb6616a80b",
        "permission_id": "693b9196-db9c-4c2d-bf3c-6345c3ec00de",
        "created_at": datetime(2024, 1, 1, 1, 0, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 1, 0, 0, tzinfo=timezone.utc),
    },
    {
        "id": "ace1690e-9950-5796-a347-e12a8813dd8b",
        "role_id": "f544f901-921e-471f-a62a-06bb6616a80b",
        "permission_id": "693b9196-db9c-4c2d-bf3c-6345c3ec00de",
        "created_at": datetime(2024, 1, 1, 2, 0, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 2, 0, 0, tzinfo=timezone.utc),
    },
    {
        "id": "38212041-bf32-5bf3-8bd2-d6402919d383",
        "role_id": "f544f901-921e-471f-a62a-06bb6616a80b",
        "permission_id": "693b9196-db9c-4c2d-bf3c-6345c3ec00de",
        "created_at": datetime(2024, 1, 1, 3, 0, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 3, 0, 0, tzinfo=timezone.utc),
    },
    {
        "id": "f2b4921c-93ec-50a2-81cb-4514d30ef435",
        "role_id": "f544f901-921e-471f-a62a-06bb6616a80b",
        "permission_id": "693b9196-db9c-4c2d-bf3c-6345c3ec00de",
        "created_at": datetime(2024, 1, 1, 4, 0, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 4, 0, 0, tzinfo=timezone.utc),
    },
    {
        "id": "88b35727-964b-5aac-b965-0d11bf255013",
        "role_id": "f544f901-921e-471f-a62a-06bb6616a80b",
        "permission_id": "693b9196-db9c-4c2d-bf3c-6345c3ec00de",
        "created_at": datetime(2024, 1, 1, 5, 0, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 5, 0, 0, tzinfo=timezone.utc),
    },
]


def _coerce_value(col: sa.Column, raw):
    """Inline seeds are already typed correctly; just return the value."""
    return raw


def upgrade() -> None:
    """Seed role_permissions with inline data instead of CSV."""
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

        # Only include keys that correspond to actual columns
        for col in table.columns:
            if col.name not in raw_row:
                continue
            row[col.name] = _coerce_value(col, raw_row[col.name])

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

    log.info("Inserted %s inline rows into %s", inserted, TABLE_NAME)


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
