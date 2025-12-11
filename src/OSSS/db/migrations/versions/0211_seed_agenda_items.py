from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0211"
down_revision = "0210"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "agenda_items"

# Inline seed rows with realistic values
# Columns:
#   meeting_id, parent_id, position, title, description,
#   linked_policy_id, linked_objective_id, time_allocated, id,
#   created_at, updated_at
SEED_ROWS = [
    {
        "meeting_id": "89ab8c9b-8c20-5b36-95db-e4e7e0a5e3b4",
        "parent_id": "ca321d07-eec1-539e-a9f4-17f7d2533683",
        "position": 1,
        "title": "Call to Order and Adoption of Agenda",
        "description": (
            "Board president calls the meeting to order, confirms quorum, and "
            "requests a motion to approve or amend the agenda for the evening."
        ),
        "linked_policy_id": "f16f9354-a0d7-55d1-bc83-2794bbe1668c",
        "linked_objective_id": "d4f0c50b-5761-5b75-95e3-ce3304ca6043",
        "time_allocated": 5,  # minutes
        "id": "ca321d07-eec1-539e-a9f4-17f7d2533683",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
    },
    {
        "meeting_id": "89ab8c9b-8c20-5b36-95db-e4e7e0a5e3b4",
        "parent_id": "f3f87987-0f85-55c3-a69c-c7fc4cb0a324",
        "position": 2,
        "title": "Student and Staff Recognition",
        "description": (
            "Celebrate winter activities, academic achievements, and staff awards. "
            "Principals introduce students and staff who will be recognized by the board."
        ),
        "linked_policy_id": "81947a25-0f5d-530b-9aba-ee4cf9dfc468",
        "linked_objective_id": "dfa3989b-685c-5c03-9946-6aec75ae30ff",
        "time_allocated": 20,
        "id": "f3f87987-0f85-55c3-a69c-c7fc4cb0a324",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
    },
    {
        "meeting_id": "89ab8c9b-8c20-5b36-95db-e4e7e0a5e3b4",
        "parent_id": "6d040a73-5d0b-5b51-8bcd-753677918961",
        "position": 3,
        "title": "Consent Agenda – Minutes, Bills, and Routine Items",
        "description": (
            "Board considers approval of the consent agenda, including prior "
            "meeting minutes, monthly financial reports, and routine contracts."
        ),
        "linked_policy_id": "07f21d25-8bbc-5dd2-a092-51aa1083d424",
        "linked_objective_id": "8a79f3e0-457c-5c8e-890c-11f9a125b463",
        "time_allocated": 15,
        "id": "6d040a73-5d0b-5b51-8bcd-753677918961",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
    },
    {
        "meeting_id": "89ab8c9b-8c20-5b36-95db-e4e7e0a5e3b4",
        "parent_id": "3a5f584f-e95a-593a-8cdd-82f445a54b38",
        "position": 4,
        "title": "Discussion: 2024–25 Academic Calendar and Instructional Hours",
        "description": (
            "Administration presents the draft academic calendar, including start "
            "and end dates, professional development days, and alignment with "
            "state instructional hour requirements. Board discusses feedback and "
            "potential revisions."
        ),
        "linked_policy_id": "a44f36f7-1207-5c0d-968f-fdcab403e59e",
        "linked_objective_id": "9ce94e2d-58f4-56f9-bd2e-ea8c5597d81e",
        "time_allocated": 30,
        "id": "3a5f584f-e95a-593a-8cdd-82f445a54b38",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
    },
    {
        "meeting_id": "89ab8c9b-8c20-5b36-95db-e4e7e0a5e3b4",
        "parent_id": "b569935b-96bd-59be-aa4f-6040e02820c6",
        "position": 5,
        "title": "Action Item: Facilities and Safety Improvements Plan",
        "description": (
            "Board reviews the recommended facilities projects for the coming year, "
            "including safety upgrades, HVAC improvements, and classroom renovations, "
            "and considers a motion for approval."
        ),
        "linked_policy_id": "f7422c9b-7cfc-54fa-8312-d0106546b223",
        "linked_objective_id": "a0a17439-a361-5d91-a290-ad2ae13fd09e",
        "time_allocated": 25,
        "id": "b569935b-96bd-59be-aa4f-6040e02820c6",
        "created_at": "2024-01-01T05:00:00Z",
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

    # Let DB cast JSON/UUID/numeric from Python primitives
    return raw


def upgrade() -> None:
    """Load seed data for agenda_items from inline SEED_ROWS.

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
