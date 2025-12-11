from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0182"
down_revision = "0181"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "alignments"

# Inline seed rows for alignments
# Columns:
# curriculum_version_id, requirement_id, alignment_level,
# evidence_url, notes, created_at, updated_at, id
SEED_ROWS = [
    {
        "curriculum_version_id": "8d122c3e-38cb-5f27-a63e-facf99bd4c49",
        "requirement_id": "29b95532-8bc5-5c94-9034-fa79ebf8f110",
        "alignment_level": "Fully aligned",
        "evidence_url": "https://curriculum.example.org/hs-math/algebra-i/scope-and-sequence",
        "notes": (
            "Algebra I scope and sequence addresses the full set of required "
            "credit-bearing math standards for the graduation requirement."
        ),
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
        "id": "7e4f331c-1104-55fd-aba7-e66bc11d2727",
    },
    {
        "curriculum_version_id": "8d122c3e-38cb-5f27-a63e-facf99bd4c49",
        "requirement_id": "29b95532-8bc5-5c94-9034-fa79ebf8f110",
        "alignment_level": "Substantially aligned",
        "evidence_url": "https://curriculum.example.org/hs-ela/grade-10/course-overview",
        "notes": (
            "Grade 10 English Language Arts course meets most graduation credit "
            "expectations; minor gaps identified in speaking and listening tasks."
        ),
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
        "id": "12fe0979-f3f4-56bb-b5aa-39c5c41c1da8",
    },
    {
        "curriculum_version_id": "8d122c3e-38cb-5f27-a63e-facf99bd4c49",
        "requirement_id": "29b95532-8bc5-5c94-9034-fa79ebf8f110",
        "alignment_level": "Partially aligned",
        "evidence_url": "https://curriculum.example.org/hs-science/biology/unit-map",
        "notes": (
            "Biology units cover core life science concepts but do not fully "
            "address state expectations for engineering and design practices."
        ),
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
        "id": "c055803d-3c92-5e5a-9321-d9f7831091e1",
    },
    {
        "curriculum_version_id": "8d122c3e-38cb-5f27-a63e-facf99bd4c49",
        "requirement_id": "29b95532-8bc5-5c94-9034-fa79ebf8f110",
        "alignment_level": "Minimally aligned",
        "evidence_url": "https://curriculum.example.org/hs-social-studies/us-history/overview",
        "notes": (
            "U.S. History materials address some state standards but lack "
            "required primary source analysis and civics-focused performance tasks."
        ),
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
        "id": "33945259-72be-5dad-b761-4016534cbef3",
    },
    {
        "curriculum_version_id": "8d122c3e-38cb-5f27-a63e-facf99bd4c49",
        "requirement_id": "29b95532-8bc5-5c94-9034-fa79ebf8f110",
        "alignment_level": "Not yet reviewed",
        "evidence_url": "https://curriculum.example.org/hs-electives/financial-literacy/syllabus",
        "notes": (
            "Financial literacy elective has been proposed for graduation credit; "
            "formal alignment review is scheduled for the next cycle."
        ),
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
        "id": "f7c3d800-8c0c-5810-a6d0-d149714c942b",
    },
]


def upgrade() -> None:
    """Load seed data for alignments from inline SEED_ROWS.

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
