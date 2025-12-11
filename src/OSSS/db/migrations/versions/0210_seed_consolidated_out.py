from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0210"
down_revision = "0209"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "consolidated_out"

# Inline seed rows with realistic data
# Columns: consolidated_answer, confidence, scores, selected_tutors,
#          rationale, created_at, id, updated_at
SEED_ROWS = [
    {
        "consolidated_answer": (
            "To add 3/8 and 1/4, first rewrite 1/4 as 2/8 so the fractions "
            "have the same denominator. Then add the numerators: 3/8 + 2/8 = 5/8. "
            "So the combined distance is 5/8 of a mile."
        ),
        "confidence": 0.94,
        "scores": {
            "tutors": {
                "82cc4801-378e-47ab-9346-09d78287b3e0": {
                    "score": 0.96,
                    "strengths": ["clear_steps", "grade_appropriate_language"],
                    "weaknesses": [],
                },
                "a3e9e030-11af-4b9e-9e7b-3a1a6fd4b2d1": {
                    "score": 0.88,
                    "strengths": ["conceptual_explanation"],
                    "weaknesses": ["slightly_wordy"],
                },
            },
            "aggregator": "weighted_average",
        },
        "selected_tutors": [
            {
                "tutor_id": "82cc4801-378e-47ab-9346-09d78287b3e0",
                "role": "math_tutor",
                "weight": 0.7,
            },
            {
                "tutor_id": "a3e9e030-11af-4b9e-9e7b-3a1a6fd4b2d1",
                "role": "concept_explainer",
                "weight": 0.3,
            },
        ],
        "rationale": (
            "Chose the fractions explanation from the math tutor as primary because "
            "it is concise, uses an appropriate common denominator strategy, and "
            "matches Grade 5 standards. Incorporated one clarifying sentence from "
            "the concept explainer to reinforce why the denominator stays the same."
        ),
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
        "id": "b9b4dcf9-a975-4f5d-a938-f2f28a98acda",
    },
    {
        "consolidated_answer": (
            "The main idea of the passage is that pollinators, like bees and "
            "butterflies, are essential for helping plants reproduce, and many of "
            "them are in danger because their habitats are disappearing."
        ),
        "confidence": 0.89,
        "scores": {
            "tutors": {
                "82cc4801-378e-47ab-9346-09d78287b3e0": {
                    "score": 0.84,
                    "strengths": ["captures_main_idea"],
                    "weaknesses": ["minor_extra_detail"],
                },
                "bbf2b7bc-4f45-4e89-9c7b-2b7c4dcf8230": {
                    "score": 0.91,
                    "strengths": ["very_concise", "aligned_with_question"],
                    "weaknesses": [],
                },
            },
            "aggregator": "max_score",
        },
        "selected_tutors": [
            {
                "tutor_id": "bbf2b7bc-4f45-4e89-9c7b-2b7c4dcf8230",
                "role": "reading_tutor",
                "weight": 0.8,
            },
            {
                "tutor_id": "82cc4801-378e-47ab-9346-09d78287b3e0",
                "role": "supporting_explainer",
                "weight": 0.2,
            },
        ],
        "rationale": (
            "Used the reading tutor’s answer as the base because it states the "
            "main idea directly and briefly. Included a small amount of language "
            "from the supporting explainer to connect pollinators to plant "
            "reproduction, which improves clarity for the student."
        ),
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
        "id": "8e7d8066-0ae9-40b9-98da-91ab91144095",
    },
    {
        "consolidated_answer": (
            "The pattern is that each term increases by 7. Starting with 4, the "
            "sequence is 4, 11, 18, 25, 32. So the next two numbers are 39 and 46."
        ),
        "confidence": 0.92,
        "scores": {
            "tutors": {
                "c3bbcfb1-7e3f-4d48-9c96-fb63a62af843": {
                    "score": 0.93,
                    "strengths": ["identifies_pattern", "extends_sequence_correctly"],
                    "weaknesses": [],
                },
                "82cc4801-378e-47ab-9346-09d78287b3e0": {
                    "score": 0.89,
                    "strengths": ["explains_difference"],
                    "weaknesses": ["less_clear_example"],
                },
            },
            "aggregator": "weighted_average",
        },
        "selected_tutors": [
            {
                "tutor_id": "c3bbcfb1-7e3f-4d48-9c96-fb63a62af843",
                "role": "pattern_tutor",
                "weight": 0.65,
            },
            {
                "tutor_id": "82cc4801-378e-47ab-9346-09d78287b3e0",
                "role": "step_explainer",
                "weight": 0.35,
            },
        ],
        "rationale": (
            "Both tutors identified the correct pattern (+7), but the pattern tutor "
            "gave a slightly clearer explanation and listed the intermediate terms. "
            "Combined both responses into a single, step-by-step explanation that "
            "shows how to extend the sequence."
        ),
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
        "id": "f29ea86e-0076-4440-a0d5-a3d5df14e63b",
    },
    {
        "consolidated_answer": (
            "Maria’s claim is supported because the data in the chart shows that "
            "the plants receiving more sunlight grew taller on average than the "
            "plants kept in the shade. This pattern held across all three trials."
        ),
        "confidence": 0.87,
        "scores": {
            "tutors": {
                "bbf2b7bc-4f45-4e89-9c7b-2b7c4dcf8230": {
                    "score": 0.88,
                    "strengths": ["references_data", "ties_back_to_claim"],
                    "weaknesses": [],
                },
                "d4b7b4e8-2ea2-4e6f-bf9f-9a54d722c199": {
                    "score": 0.82,
                    "strengths": ["mentions_trials"],
                    "weaknesses": ["less_specific_about_averages"],
                },
            },
            "aggregator": "weighted_average",
        },
        "selected_tutors": [
            {
                "tutor_id": "bbf2b7bc-4f45-4e89-9c7b-2b7c4dcf8230",
                "role": "science_tutor",
                "weight": 0.7,
            },
            {
                "tutor_id": "d4b7b4e8-2ea2-4e6f-bf9f-9a54d722c199",
                "role": "data_checker",
                "weight": 0.3,
            },
        ],
        "rationale": (
            "Prioritized the explanation that directly connects the chart data to "
            "Maria’s claim. Added a brief reference to multiple trials from the "
            "second tutor’s answer to strengthen the idea that the pattern is "
            "consistent, not just a one-time result."
        ),
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
        "id": "97da8c78-b427-48e5-9442-c5c20cb82315",
    },
    {
        "consolidated_answer": (
            "A good summary of this paragraph is: Liam was nervous about starting "
            "at a new school, but meeting a friendly classmate on the first day "
            "helped him feel more confident."
        ),
        "confidence": 0.9,
        "scores": {
            "tutors": {
                "bbf2b7bc-4f45-4e89-9c7b-2b7c4dcf8230": {
                    "score": 0.9,
                    "strengths": ["captures_key_events", "keeps_summary_brief"],
                    "weaknesses": [],
                },
                "e2dfe1de-7e0a-438a-bb15-86989c0e02f8": {
                    "score": 0.86,
                    "strengths": ["emphasizes_feelings"],
                    "weaknesses": ["adds_extra_detail"],
                },
            },
            "aggregator": "weighted_average",
        },
        "selected_tutors": [
            {
                "tutor_id": "bbf2b7bc-4f45-4e89-9c7b-2b7c4dcf8230",
                "role": "reading_tutor",
                "weight": 0.75,
            },
            {
                "tutor_id": "e2dfe1de-7e0a-438a-bb15-86989c0e02f8",
                "role": "SEL_support_tutor",
                "weight": 0.25,
            },
        ],
        "rationale": (
            "The reading tutor’s summary is closest to the target length (one–two "
            "sentences) and includes the central problem (nervous about a new "
            "school) and solution (meeting a friendly classmate). Added a small "
            "phrase from the SEL tutor to highlight the emotional shift, which "
            "supports comprehension of character feelings."
        ),
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
        "id": "58423987-339d-4ef6-8682-ecff1dedba4c",
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

    # Let DB cast JSON/UUID/numeric from Python primitives
    return raw


def upgrade() -> None:
    """Load seed data for consolidated_out from inline SEED_ROWS.

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
