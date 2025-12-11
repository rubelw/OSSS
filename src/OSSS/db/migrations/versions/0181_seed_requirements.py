from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0181"
down_revision = "0180"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "requirements"

# Inline seed rows for requirements
# Columns:
# state_code, title, category, description,
# effective_date, reference_url, attributes,
# created_at, updated_at, id
SEED_ROWS = [
    {
        "state_code": "al",
        "title": "High School Graduation Credit Requirements (Sample)",
        "category": "Graduation",
        "description": (
            "Sample requirement describing the minimum number of credits "
            "a student must earn in English, mathematics, science, social "
            "studies, and electives to receive a standard high school diploma."
        ),
        "effective_date": "2024-01-02",
        "reference_url": "https://www.alabamaachieves.org/graduation-requirements",
        "attributes": {},
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
        "id": "29b95532-8bc5-5c94-9034-fa79ebf8f110",
    },
    {
        "state_code": "al",
        "title": "Compulsory School Attendance Age (Sample)",
        "category": "Attendance",
        "description": (
            "Sample requirement establishing compulsory school attendance "
            "for students from age 6 through age 17, with limited exemptions "
            "for graduation, transfer, or approved alternative programs."
        ),
        "effective_date": "2024-01-03",
        "reference_url": "https://www.alabamaachieves.org/student-services/attendance",
        "attributes": {},
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
        "id": "9736e4ce-be44-5f24-a3bd-b5cd71fde87c",
    },
    {
        "state_code": "al",
        "title": "Minimum Instructional Time per School Year (Sample)",
        "category": "InstructionalTime",
        "description": (
            "Sample requirement specifying that each district shall provide "
            "no fewer than 180 instructional days, or an equivalent number "
            "of instructional hours, during the regular school year."
        ),
        "effective_date": "2024-01-04",
        "reference_url": "https://www.alabamaachieves.org/calendar-requirements",
        "attributes": {},
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
        "id": "432d16b4-b71d-5758-a4e0-459198b1f74c",
    },
    {
        "state_code": "al",
        "title": "Student Immunization and Health Records (Sample)",
        "category": "Health",
        "description": (
            "Sample requirement that school systems maintain current "
            "immunization certificates or approved exemptions for all "
            "enrolled students and verify records on initial enrollment."
        ),
        "effective_date": "2024-01-05",
        "reference_url": "https://www.alabamaachieves.org/student-services/health",
        "attributes": {},
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
        "id": "6280ba18-8bcb-5842-904e-ffbf4f4b4b20",
    },
    {
        "state_code": "al",
        "title": "School Safety and Emergency Preparedness (Sample)",
        "category": "Safety",
        "description": (
            "Sample requirement that each school maintain a written safety "
            "and crisis response plan, conduct regular emergency drills, "
            "and review procedures with staff at least annually."
        ),
        "effective_date": "2024-01-06",
        "reference_url": "https://www.alabamaachieves.org/school-safety",
        "attributes": {},
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
        "id": "29e4083c-dfb2-551b-a50c-1279a6543137",
    },
]


def upgrade() -> None:
    """Load seed data for requirements from inline SEED_ROWS.

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
    for raw_row in SEED_ROWS:
        # Only include columns that actually exist on the table
        row: dict[str, object] = {
            col.name: raw_row[col.name]
            for col in table.columns
            if col.name in raw_row
        }

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

    log.info(
        "Inserted %s rows into %s from inline SEED_ROWS",
        inserted,
        TABLE_NAME,
    )


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
