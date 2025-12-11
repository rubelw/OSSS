from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0207"
down_revision = "0206"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "turn_in"

# Inline seed rows with realistic data
# Columns: session_id, prompt, objective_code, tutors, created_at, id, updated_at
SEED_ROWS = [
    {
        "session_id": "28da96d8-0d7c-5def-afa2-7c2996853fb2",
        "prompt": "I’m stuck on adding fractions with different denominators. Can you walk me through an example?",
        "objective_code": "MATH-5.NF.1",
        "tutors": {
            "primary": "ai_math_tutor",
            "human_reviewers": ["smith_j"],
            "mode": "fraction_scaffolding",
        },
        "created_at": "2024-01-01T01:00:00Z",
        "id": "9add3d1b-a74b-5b25-b96c-efd3d36da222",
        "updated_at": "2024-01-01T01:00:00Z",
    },
    {
        "session_id": "28da96d8-0d7c-5def-afa2-7c2996853fb2",
        "prompt": "How do I find a common denominator for 2/3 and 5/6?",
        "objective_code": "MATH-5.NF.1",
        "tutors": {
            "primary": "ai_math_tutor",
            "human_reviewers": ["smith_j", "lee_k"],
            "mode": "guided_example",
        },
        "created_at": "2024-01-01T02:00:00Z",
        "id": "408d597f-1303-5efa-9bf1-e4cc499c8e34",
        "updated_at": "2024-01-01T02:00:00Z",
    },
    {
        "session_id": "28da96d8-0d7c-5def-afa2-7c2996853fb2",
        "prompt": "Can you check if I added these fractions correctly: 3/4 + 1/8?",
        "objective_code": "MATH-5.NF.2",
        "tutors": {
            "primary": "ai_math_tutor",
            "mode": "answer_check",
            "flags": {"show_step_feedback": True},
        },
        "created_at": "2024-01-01T03:00:00Z",
        "id": "923bcc54-568d-5386-8122-2aa6e33d79d1",
        "updated_at": "2024-01-01T03:00:00Z",
    },
    {
        "session_id": "28da96d8-0d7c-5def-afa2-7c2996853fb2",
        "prompt": "Explain why 2/3 and 4/6 are equivalent fractions using a picture.",
        "objective_code": "MATH-5.NF.3",
        "tutors": {
            "primary": "ai_math_tutor",
            "mode": "conceptual_explanation",
            "supports_images": True,
        },
        "created_at": "2024-01-01T04:00:00Z",
        "id": "c0e958c5-2d23-5a35-859f-3710ddee9fa7",
        "updated_at": "2024-01-01T04:00:00Z",
    },
    {
        "session_id": "28da96d8-0d7c-5def-afa2-7c2996853fb2",
        "prompt": "Give me a word problem that uses adding fractions with unlike denominators.",
        "objective_code": "MATH-5.NF.4",
        "tutors": {
            "primary": "ai_math_tutor",
            "mode": "problem_generation",
            "difficulty": "on_level",
        },
        "created_at": "2024-01-01T05:00:00Z",
        "id": "28a9fb12-a983-5915-a7b0-1b25e9f73deb",
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
    """Load seed data for turn_in from inline SEED_ROWS.

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
