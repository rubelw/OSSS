from __future__ import annotations

import logging
import os

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0087"
down_revision = "0086"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "goals"
CSV_FILE = os.path.join(os.path.dirname(__file__), "csv", f"{TABLE_NAME}.csv")

# Inline seed data for goals
SEED_ROWS = [
    {
        "plan_id": "7f2eb6b4-2c3e-4c78-9d7a-90bb2b67e21d",
        "name": "Increase Student Achievement",
        "description": (
            "Improve academic performance by strengthening instructional practices, "
            "increasing access to high-quality curriculum, and using data-driven interventions."
        ),
        "id": "475010fd-e5b0-53d4-ba80-fe79851cf581",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
    },
    {
        "plan_id": "7f2eb6b4-2c3e-4c78-9d7a-90bb2b67e21d",
        "name": "Enhance Student Well-Being",
        "description": (
            "Support the social-emotional and mental health needs of all students through "
            "expanded counseling services, SEL programming, and supportive environments."
        ),
        "id": "125234d5-ce50-5e45-9d9a-c4927a0736e9",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
    },
    {
        "plan_id": "7f2eb6b4-2c3e-4c78-9d7a-90bb2b67e21d",
        "name": "Strengthen Community Engagement",
        "description": (
            "Increase transparency and communication with families and the broader community "
            "through improved outreach, regular updates, and meaningful engagement opportunities."
        ),
        "id": "01e40b7b-50e7-58b6-b984-6f19ef9925c1",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
    },
    {
        "plan_id": "7f2eb6b4-2c3e-4c78-9d7a-90bb2b67e21d",
        "name": "Support High-Quality Staff",
        "description": (
            "Recruit, develop, and retain exceptional educators and staff by providing ongoing "
            "professional development, competitive compensation, and supportive working conditions."
        ),
        "id": "f10b842e-74b8-5f3b-aa22-967737cf87b3",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
    },
    {
        "plan_id": "7f2eb6b4-2c3e-4c78-9d7a-90bb2b67e21d",
        "name": "Optimize Facilities and Resources",
        "description": (
            "Ensure district facilities, technology, and operational systems effectively support "
            "learning, safety, and long-term sustainability."
        ),
        "id": "b20cb698-8843-5c7a-8f5c-fa746d9e0e43",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
    },
]


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion from CSV-style string to appropriate Python value."""
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
            log.warning("Invalid boolean for %s.%s: %r; using NULL", TABLE_NAME, col.name, raw)
            return None
        return bool(raw)

    # Otherwise, pass raw through and let DB cast
    return raw


def upgrade() -> None:
    """Load seed data for goals from inline SEED_ROWS.

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

    log.info("Inserted %s rows into %s (inline seed)", inserted, TABLE_NAME)


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
