from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0076"
down_revision = "0075"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "courses"

# Inline seed data for courses
SEED_ROWS = [
    {
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "subject_id": "9002fc8b-e381-5bc4-8a76-902c81686aac",
        "name": "English III",
        "code": "ENG3-101",
        "credit_hours": "2",
        "user_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "section": "Section 1 - Junior English",
        "description": "Junior-level English course focusing on nonfiction reading, argumentative writing, and research skills.",
        "room": "HS-201",
        "owner_id": "courses_owner_id_1",
        "course_state": "PROVISIONED",
        "enrollment_code": "ENG3-24-1",
        "alternate_link": "https://classroom.google.com/c/ENG3-24-1",
        "calendar_id": "06ccb9f6-6bd6-5e3a-86c4-bbdf6a17c36b",
        "creation_time": "2024-01-01T01:00:00Z",
        "update_time": "2024-01-01T01:00:00Z",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
        "id": "a4cddcde-b046-5dd4-8255-593ba99983c6",
    },
    {
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "subject_id": "9002fc8b-e381-5bc4-8a76-902c81686aac",
        "name": "Business Law",
        "code": "BUSLAW-201",
        "credit_hours": "1",
        "user_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "section": "Section 1 - Business Law",
        "description": "Overview of the American legal system, contracts, consumer rights, and legal responsibilities in everyday life.",
        "room": "HS-115",
        "owner_id": "courses_owner_id_2",
        "course_state": "ACTIVE",
        "enrollment_code": "BUSLAW-24-1",
        "alternate_link": "https://classroom.google.com/c/BUSLAW-24-1",
        "calendar_id": "06ccb9f6-6bd6-5e3a-86c4-bbdf6a17c36b",
        "creation_time": "2024-01-01T02:00:00Z",
        "update_time": "2024-01-01T02:00:00Z",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
        "id": "aabd552e-f9c2-5779-8fd0-b082278f9823",
    },
    {
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "subject_id": "9002fc8b-e381-5bc4-8a76-902c81686aac",
        "name": "Fashions II",
        "code": "FASH-302",
        "credit_hours": "1",
        "user_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "section": "Section 1 - Advanced Fashion",
        "description": "Advanced apparel and fashion design course building on Fashions I; focuses on pattern use, garment construction, and the fashion industry.",
        "room": "HS-106",
        "owner_id": "courses_owner_id_3",
        "course_state": "ARCHIVED",
        "enrollment_code": "FASH2-23-1",
        "alternate_link": "https://classroom.google.com/c/FASH2-23-1",
        "calendar_id": "06ccb9f6-6bd6-5e3a-86c4-bbdf6a17c36b",
        "creation_time": "2024-01-01T03:00:00Z",
        "update_time": "2024-01-01T03:00:00Z",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
        "id": "f97f6a95-173a-511e-a03e-7c11fe8ec176",
    },
    {
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "subject_id": "9002fc8b-e381-5bc4-8a76-902c81686aac",
        "name": "Independent Living",
        "code": "INDEP-210",
        "credit_hours": "1",
        "user_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "section": "Section 1 - Independent Living",
        "description": "Practical life-skills course covering budgeting, renting, basic cooking, personal health, and planning for life after high school.",
        "room": "HS-120",
        "owner_id": "courses_owner_id_4",
        "course_state": "DECLINED",
        "enrollment_code": "INDEP-24-1",
        "alternate_link": "https://classroom.google.com/c/INDEP-24-1",
        "calendar_id": "06ccb9f6-6bd6-5e3a-86c4-bbdf6a17c36b",
        "creation_time": "2024-01-01T04:00:00Z",
        "update_time": "2024-01-01T04:00:00Z",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
        "id": "795fbb81-7d0c-59b9-a898-5327ce1fa10f",
    },
    {
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "subject_id": "9002fc8b-e381-5bc4-8a76-902c81686aac",
        "name": "Financial Literacy II",
        "code": "FINLIT-402",
        "credit_hours": "1",
        "user_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "section": "Section 1 - Financial Lit 2",
        "description": "Upper-level personal finance course focused on investing, credit, long-term planning, and real-world financial decision-making.",
        "room": "HS-118",
        "owner_id": "courses_owner_id_5",
        "course_state": "SUSPENDED",
        "enrollment_code": "FIN2-24-1",
        "alternate_link": "https://classroom.google.com/c/FIN2-24-1",
        "calendar_id": "06ccb9f6-6bd6-5e3a-86c4-bbdf6a17c36b",
        "creation_time": "2024-01-01T05:00:00Z",
        "update_time": "2024-01-01T05:00:00Z",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
        "id": "2b257e6c-ed3e-5cbd-ae97-1f21a6d8d2d9",
    },
]


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion from Python value to appropriate DB-bound value."""
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
    """Load seed data for courses from inline SEED_ROWS.

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

    if not SEED_ROWS:
        log.info("No seed rows defined for %s", TABLE_NAME)
        return

    inserted = 0
    for raw_row in SEED_ROWS:
        row: dict[str, object] = {}

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
                "Skipping row for %s due to error: %s. Row: %s",
                TABLE_NAME,
                exc,
                raw_row,
            )

    log.info("Inserted %s rows into %s (inline seed)", inserted, TABLE_NAME)


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
