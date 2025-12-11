from __future__ import annotations

import csv  # kept for consistency with other migrations, though unused for seeding
import logging
import os
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0289"
down_revision = "0288"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "family_portal_access"
CSV_FILE = os.path.join(os.path.dirname(__file__), "csv", f"{TABLE_NAME}.csv")

# Inline seed data
# Columns: id, guardian_id, student_id, permissions, created_at, updated_at
SEED_ROWS = [
    {
        "id": "064c7c11-60bc-57bb-bde2-86d480249eaa",
        "guardian_id": "ba756e0b-7456-5d58-bac4-e6afdd286c3d",
        "student_id": "d4f53e78-1012-5322-a4f3-4bca2efc51be",
        "permissions": "view_grades,view_attendance,view_schedule",
        "created_at": datetime(2024, 1, 1, 1, 0, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 1, 0, 0, tzinfo=timezone.utc),
    },
    {
        "id": "413ad0e4-a2c7-5622-ab98-099f7f7dde8c",
        "guardian_id": "ba756e0b-7456-5d58-bac4-e6afdd286c3d",
        "student_id": "d4f53e78-1012-5322-a4f3-4bca2efc51be",
        "permissions": "view_grades,view_attendance,view_schedule,view_discipline",
        "created_at": datetime(2024, 1, 1, 2, 0, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 2, 0, 0, tzinfo=timezone.utc),
    },
    {
        "id": "ceb58700-6a4c-5f7d-91d4-6239d3f9048c",
        "guardian_id": "ba756e0b-7456-5d58-bac4-e6afdd286c3d",
        "student_id": "d4f53e78-1012-5322-a4f3-4bca2efc51be",
        "permissions": "view_grades,view_attendance,view_schedule,view_fees",
        "created_at": datetime(2024, 1, 1, 3, 0, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 3, 0, 0, tzinfo=timezone.utc),
    },
    {
        "id": "70c83d06-c0c4-564e-8065-28dd7132a132",
        "guardian_id": "ba756e0b-7456-5d58-bac4-e6afdd286c3d",
        "student_id": "d4f53e78-1012-5322-a4f3-4bca2efc51be",
        "permissions": "view_grades,view_attendance,update_contact_info",
        "created_at": datetime(2024, 1, 1, 4, 0, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 4, 0, 0, tzinfo=timezone.utc),
    },
    {
        "id": "26106308-9183-5fda-a880-08e2341c1409",
        "guardian_id": "ba756e0b-7456-5d58-bac4-e6afdd286c3d",
        "student_id": "d4f53e78-1012-5322-a4f3-4bca2efc51be",
        "permissions": "full_access",  # includes grades, attendance, schedule, fees, contacts
        "created_at": datetime(2024, 1, 1, 5, 0, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, 5, 0, 0, tzinfo=timezone.utc),
    },
]


def _coerce_value(col: sa.Column, raw):
    """For inline seeds we already provide appropriately-typed values."""
    return raw


def upgrade() -> None:
    """Seed family_portal_access with realistic example rows."""
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

        # Only keep keys that correspond to actual columns
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

    log.info("Inserted %s rows into %s", inserted, TABLE_NAME)


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
