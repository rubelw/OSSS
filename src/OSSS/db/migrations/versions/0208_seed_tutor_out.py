from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0208"
down_revision = "0207"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "tutor_out"

# Inline seed rows with realistic data
# Columns: tutor_id, response, evidence, score, confidence, created_at, id, updated_at
SEED_ROWS = [
    {
        "tutor_id": "82cc4801-378e-47ab-9346-09d78287b3e0",
        "response": (
            "Great start! When adding 2/3 and 1/6, first rewrite 2/3 as 4/6 so the "
            "denominators match. Then add 4/6 + 1/6 = 5/6."
        ),
        "evidence": {
            "rubric_alignment": {
                "mathematical_correctness": True,
                "grade_level_appropriate": True,
                "clear_explanation": True,
            },
            "referenced_objectives": ["MATH-5.NF.1"],
            "source_session_id": "28da96d8-0d7c-5def-afa2-7c2996853fb2",
        },
        "score": 5,
        "confidence": 5,
        "created_at": "2024-01-01T01:00:00Z",
        "id": "4c11157c-895f-560a-b645-6495981eac3c",
        "updated_at": "2024-01-01T01:00:00Z",
    },
    {
        "tutor_id": "82cc4801-378e-47ab-9346-09d78287b3e0",
        "response": (
            "To find a common denominator for 3/4 and 5/8, use 8. Rewrite 3/4 as 6/8, "
            "then add 6/8 + 5/8 = 11/8, which is 1 3/8 as a mixed number."
        ),
        "evidence": {
            "rubric_alignment": {
                "mathematical_correctness": True,
                "grade_level_appropriate": True,
                "clear_explanation": True,
            },
            "referenced_objectives": ["MATH-5.NF.1", "MATH-5.NF.2"],
            "hints_used": 1,
        },
        "score": 4,
        "confidence": 4,
        "created_at": "2024-01-01T02:00:00Z",
        "id": "49af9a5a-338f-59c4-921c-8da1071e17d5",
        "updated_at": "2024-01-01T02:00:00Z",
    },
    {
        "tutor_id": "82cc4801-378e-47ab-9346-09d78287b3e0",
        "response": (
            "You said 3/4 + 1/8 = 4/12, but that’s not correct. First rewrite 3/4 as 6/8. "
            "Then 6/8 + 1/8 = 7/8, so the correct answer is 7/8."
        ),
        "evidence": {
            "rubric_alignment": {
                "mathematical_correctness": True,
                "misconception_addressed": "added numerators and denominators",
                "clear_explanation": True,
            },
            "referenced_objectives": ["MATH-5.NF.2"],
            "feedback_type": "error_correction",
        },
        "score": 5,
        "confidence": 4,
        "created_at": "2024-01-01T03:00:00Z",
        "id": "6ec4785c-fbb7-567f-9261-80a5e4c80fba",
        "updated_at": "2024-01-01T03:00:00Z",
    },
    {
        "tutor_id": "82cc4801-378e-47ab-9346-09d78287b3e0",
        "response": (
            "Imagine a rectangle split into 3 equal columns. Shade 2 columns to show 2/3. "
            "Now split each column into 2 rows. You’ll have 6 equal parts with 4 shaded, "
            "so 2/3 is the same as 4/6."
        ),
        "evidence": {
            "rubric_alignment": {
                "visual_reasoning": True,
                "conceptual_depth": True,
                "student_friendly_language": True,
            },
            "referenced_objectives": ["MATH-5.NF.3"],
            "supports_images": True,
        },
        "score": 5,
        "confidence": 5,
        "created_at": "2024-01-01T04:00:00Z",
        "id": "af04be27-1adf-5c69-ba74-bffcf676d4e4",
        "updated_at": "2024-01-01T04:00:00Z",
    },
    {
        "tutor_id": "82cc4801-378e-47ab-9346-09d78287b3e0",
        "response": (
            "Here’s a word problem: Mia ran 2/5 of a mile in the morning and 3/10 of a mile "
            "after school. How far did she run in all? (Hint: find a common denominator.)"
        ),
        "evidence": {
            "rubric_alignment": {
                "real_world_context": True,
                "grade_level_appropriate": True,
                "targets_fraction_addition": True,
            },
            "referenced_objectives": ["MATH-5.NF.2", "MATH-5.NF.4"],
            "difficulty": "on_level",
        },
        "score": 4,
        "confidence": 4,
        "created_at": "2024-01-01T05:00:00Z",
        "id": "4ad3026a-0ef5-5c0e-90e6-ae7bf8b543ea",
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

    # Otherwise, pass raw through and let DB cast (covers JSONB, UUID, etc.)
    return raw


def upgrade() -> None:
    """Load seed data for tutor_out from inline SEED_ROWS.

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

    rows = SEED_ROWS
    if not rows:
        log.info("No inline seed rows defined for %s", TABLE_NAME)
        return

    inserted = 0
    for raw_row in rows:
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

    log.info("Inserted %s inline seed rows into %s", inserted, TABLE_NAME)


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
