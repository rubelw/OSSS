from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0209"
down_revision = "0208"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "tutor_spec"

# Inline seed rows with realistic data
# Columns: tutor_id, spec_json, description, created_at, updated_at, id
SEED_ROWS = [
    {
        "tutor_id": "82cc4801-378e-47ab-9346-09d78287b3e0",
        "spec_json": {
            "role": "math_tutor",
            "display_name": "Grade 5 Math Tutor",
            "subject": "Mathematics",
            "grade_levels": ["5"],
            "focus_standards": ["MATH-5.NF.1", "MATH-5.NF.2", "MATH-5.NF.3"],
            "tone": "encouraging",
            "guidelines": [
                "Use clear, student-friendly language.",
                "Show each step when modeling a solution.",
                "Ask a quick check-for-understanding question at the end.",
            ],
            "constraints": {
                "max_steps_per_explanation": 5,
                "avoid": [
                    "giving the final answer immediately without reasoning",
                    "using advanced algebraic notation that is above grade level",
                ],
            },
            "supports": {
                "hints": True,
                "multiple_representations": ["number_line", "area_model", "equation"],
            },
        },
        "description": (
            "Default specification for the Grade 5 fractions tutor. "
            "Targets fraction addition/subtraction and word problems with an "
            "encouraging, step-by-step style."
        ),
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
        "id": "87e4d8d4-e6b6-5965-a44a-c5e72d7f4392",
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

    # For JSONB, UUID, etc., let the DB cast from native Python types
    return raw


def upgrade() -> None:
    """Load seed data for tutor_spec from inline SEED_ROWS.

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
