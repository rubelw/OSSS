from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0042"
down_revision = "0041"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "user_profiles"

# Inline seed data for user_profiles
# Columns: user_id, primary_email, full_name, photo_url,
#          is_teacher, is_student, created_at, updated_at, id
SEED_ROWS = [
    {
        "user_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",  # Michael Smith (Teacher)
        "primary_email": "michaelsmith@dcgschools.org",
        "full_name": "Michael Smith",
        "photo_url": "user_profiles_photo_url_1",
        "is_teacher": "true",
        "is_student": "false",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
        "id": "bf98bfb1-547f-5bd5-9c70-2b789e0bfb4b",
    },
    {
        "user_id": "861af025-3009-4c30-8455-644ae633c497",  # Sarah Johnson (Principal)
        "primary_email": "sarahjohnson@dcgschools.org",
        "full_name": "Sarah Johnson",
        "photo_url": "user_profiles_photo_url_2",
        "is_teacher": "false",
        "is_student": "false",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
        "id": "c16445fe-670c-5225-91b8-765ae3b7fec2",
    },
    {
        "user_id": "e2d66cd0-b0c1-4f8d-b1a7-faef4804f7d9",  # James Williams (Superintendent)
        "primary_email": "jameswilliams@dcgschools.org",
        "full_name": "James Williams",
        "photo_url": "user_profiles_photo_url_3",
        "is_teacher": "false",
        "is_student": "false",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
        "id": "27e38c8d-d0f3-550d-8c7a-614e63d960d3",
    },
    {
        "user_id": "22838cc6-88af-472f-9723-2ef1b2804d6e",  # Emily Brown (Board Member)
        "primary_email": "emilybrown@dcgschools.org",
        "full_name": "Emily Brown",
        "photo_url": "user_profiles_photo_url_4",
        "is_teacher": "false",
        "is_student": "false",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
        "id": "692dfafb-bcfa-560e-84d8-be00ce5d1b97",
    },
    {
        "user_id": "ca72277c-0b76-4560-b6aa-3eb616efe63e",  # David Jones (System Admin)
        "primary_email": "davidjones@dcgschools.org",
        "full_name": "David Jones",
        "photo_url": "user_profiles_photo_url_5",
        "is_teacher": "false",
        "is_student": "false",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
        "id": "8759b06a-0165-5e63-96b9-07682bf2ad11",
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
            log.warning(
                "Invalid boolean for %s.%s: %r; using NULL",
                TABLE_NAME,
                col.name,
                raw,
            )
            return None
        return bool(raw)

    # Otherwise, pass raw through and let DB cast (UUIDs, timestamps, etc.)
    return raw


def upgrade() -> None:
    """Load seed data for user_profiles from inline SEED_ROWS.

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
                # Let server defaults handle anything not in SEED_ROWS
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
                "Skipping row for %s due to error: %s. Row: %s",
                TABLE_NAME,
                exc,
                raw_row,
            )

    log.info("Inserted %s rows into %s from inline seed data", inserted, TABLE_NAME)


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
