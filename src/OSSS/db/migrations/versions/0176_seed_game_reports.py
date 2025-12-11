from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0176"
down_revision = "0175"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "game_reports"

# Inline seed rows for game_reports
# Columns: game_id, report_type, content, created_at, updated_at, id
SEED_ROWS = [
    {
        "game_id": "35b62837-a339-5111-aa05-37dfbcebd7e7",
        "report_type": "final_score_summary",
        "content": (
            "Home 62 – Visitors 58. The home team led for most of the second half, "
            "closing the game with strong defensive possessions and timely free throws. "
            "Both teams traded leads early before the hosts pulled ahead late in the third quarter."
        ),
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
        "id": "ae09c1e9-df70-5d81-8539-aa319ee1c468",
    },
    {
        "game_id": "35b62837-a339-5111-aa05-37dfbcebd7e7",
        "report_type": "quarter_by_quarter",
        "content": (
            "Q1: Home 14 – Visitors 15. Q2: Home 28 – Visitors 27. "
            "Q3: Home 45 – Visitors 42. Q4: Home 62 – Visitors 58. "
            "Momentum shifted at the start of the third quarter when the home team "
            "opened with an 8–0 run sparked by back-to-back three-point shots."
        ),
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
        "id": "e411b152-d635-5b34-b8b3-9b9dbe0b3b48",
    },
    {
        "game_id": "35b62837-a339-5111-aa05-37dfbcebd7e7",
        "report_type": "coach_postgame_comments",
        "content": (
            "Head Coach: “I’m proud of how our players responded in the second half. "
            "We shared the ball, defended without fouling, and stayed composed down the stretch. "
            "There are still details to clean up offensively, but this is a solid conference win.”"
        ),
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
        "id": "1d29ded0-62a0-52e8-8949-a75560921b3e",
    },
    {
        "game_id": "35b62837-a339-5111-aa05-37dfbcebd7e7",
        "report_type": "injury_and_incident_report",
        "content": (
            "No major injuries were reported. One player left briefly in the second quarter "
            "with a minor ankle sprain but returned after evaluation and taping. "
            "Officials reported no technical fouls, ejections, or spectator incidents."
        ),
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
        "id": "e11f61d3-614d-5f81-9b51-d81a5955f90a",
    },
    {
        "game_id": "35b62837-a339-5111-aa05-37dfbcebd7e7",
        "report_type": "attendance_and_operations",
        "content": (
            "Announced attendance: 742. Concessions and ticketing operated without issue. "
            "Parking lots were cleared within 25 minutes of the final buzzer. "
            "Event staff reported positive spectator behavior and no safety concerns."
        ),
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
        "id": "1189feef-f319-5513-9e95-2e16926fdc4a",
    },
]


def upgrade() -> None:
    """Load seed data for game_reports from inline SEED_ROWS.

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

        # Explicit nested transaction (SAVEPOINT)
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

    log.info("Inserted %s rows into %s from inline SEED_ROWS", inserted, TABLE_NAME)


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
