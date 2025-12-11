from __future__ import annotations

import csv  # kept for consistency with other migrations, even if unused
import logging
import os

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0227"
down_revision = "0226"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "plan_assignments"
CSV_FILE = None  # seeding from inline data instead of CSV


# Inline seed data with realistic values:
# id, entity_type, entity_id, assignee_type, assignee_id
SEED_ROWS = [
    {
        # Assign a district strategic goal to the superintendent
        "id": "23399eaa-b996-4524-b848-09ce052eedce",
        "entity_type": "district_goal",
        "entity_id": "5e7bf264-e3f5-569e-873c-11e9101db4e0",
        "assignee_type": "person",
        "assignee_id": "7846174e-6bf9-5887-9093-1018becbaeda",
    },
    {
        # Assign a board priority to the Board President role
        "id": "0d44ab8e-c15a-44a1-bd1a-4e4a400ab578",
        "entity_type": "board_priority",
        "entity_id": "9c2f39ed-a90c-57f9-9f72-ac60af541f04",
        "assignee_type": "role",
        "assignee_id": "1aaacd14-9e48-5b7e-aacd-51995393de36",
    },
    {
        # Assign a strategic initiative to the Teaching & Learning department
        "id": "657d4bd9-749a-4ac2-91d8-a6e6a97aff05",
        "entity_type": "strategic_initiative",
        "entity_id": "56032eab-df40-5d3b-b74a-cdb9c0ee21e0",
        "assignee_type": "department",
        "assignee_id": "7db480b8-e53e-5325-ae35-c27ec08c70c2",
    },
    {
        # Assign an action step to an individual principal
        "id": "609c8507-a464-4a7f-9434-60b06a7719f3",
        "entity_type": "action_step",
        "entity_id": "9861a85b-20d1-5559-ace3-c808155dd619",
        "assignee_type": "person",
        "assignee_id": "30738e95-dd3e-5cc6-ae96-7092fc487096",
    },
    {
        # Assign a key performance measure to the district leadership team
        "id": "614b1050-8725-43ed-8fec-81f92b6c0ad3",
        "entity_type": "performance_measure",
        "entity_id": "80397dc8-6328-5a65-bcb3-88435b45af2a",
        "assignee_type": "team",
        "assignee_id": "17198e5a-a06f-5bad-b163-505981f18832",
    },
]


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion from inline seed values to appropriate Python/DB values."""
    if raw == "" or raw is None:
        return None

    t = col.type

    # Boolean handling (for future-proofing if booleans are added later)
    if isinstance(t, sa.Boolean):
        if isinstance(raw, str):
            v = raw.strip().lower()
            if v in ("true", "t", "1", "yes", "y"):
                return True
            if v in ("false", "f", "0", "no", "n"):
                return False
            log.warning(
                "Invalid boolean for %s.%s: %r; using NULL", TABLE_NAME, col.name, raw
            )
            return None
        return bool(raw)

    # Otherwise, let the DB cast (UUID, text, etc.)
    return raw


def upgrade() -> None:
    """Load seed data for plan_assignments from inline SEED_ROWS (no CSV)."""
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
