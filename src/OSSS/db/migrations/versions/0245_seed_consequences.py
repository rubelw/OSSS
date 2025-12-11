from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0245"
down_revision = "0244"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "consequences"

# Inline, realistic seed rows
# consequence_code values must match consequence_types.code as derived in 0009:
#   WARNING
#   LUNCH_DETENTION
#   AFTER_SCHOOL_DETENTION
#   IN_SCHOOL_SUSPENSION
#   OUT_OF_SCHOOL_SUSPENSION
SEED_ROWS = [
    {
        "incident_id": "9868063c-5b19-5bb6-aed1-927b1bc56093",
        "participant_id": "7333748d-b32c-5724-ab8f-c769e06693d5",
        "consequence_code": "LUNCH_DETENTION",
        "start_date": "2024-01-02",
        "end_date": "2024-01-02",
        "notes": "Assigned one day of lunch detention for repeated classroom disruptions.",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
        "id": "0aa35c13-60e8-5859-9778-de536ee73d11",
    },
    {
        "incident_id": "9868063c-5b19-5bb6-aed1-927b1bc56093",
        "participant_id": "7333748d-b32c-5724-ab8f-c769e06693d5",
        "consequence_code": "AFTER_SCHOOL_DETENTION",
        "start_date": "2024-01-03",
        "end_date": "2024-01-03",
        "notes": "After-school detention for failure to serve prior consequence on time.",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
        "id": "b875651d-04b4-5c7b-b197-7ff59ace775b",
    },
    {
        "incident_id": "9868063c-5b19-5bb6-aed1-927b1bc56093",
        "participant_id": "7333748d-b32c-5724-ab8f-c769e06693d5",
        "consequence_code": "IN_SCHOOL_SUSPENSION",
        "start_date": "2024-01-04",
        "end_date": "2024-01-04",
        "notes": "One day of in-school suspension for disrespect toward staff.",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
        "id": "e3ffefde-d3c0-5da6-a2b3-1d284988e607",
    },
    {
        "incident_id": "9868063c-5b19-5bb6-aed1-927b1bc56093",
        "participant_id": "7333748d-b32c-5724-ab8f-c769e06693d5",
        "consequence_code": "OUT_OF_SCHOOL_SUSPENSION",
        "start_date": "2024-01-05",
        "end_date": "2024-01-05",
        "notes": "Short-term out-of-school suspension following repeated serious behavior incidents.",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
        "id": "27938692-6066-53dd-bd0f-fd0d3ed08130",
    },
    {
        "incident_id": "9868063c-5b19-5bb6-aed1-927b1bc56093",
        "participant_id": "7333748d-b32c-5724-ab8f-c769e06693d5",
        "consequence_code": "WARNING",
        "start_date": "2024-01-06",
        "end_date": "2024-01-06",
        "notes": "Formal written warning issued after parent conference outlining future expectations.",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
        "id": "d2f0e0ac-9c66-5b2c-9171-9b1396a1eaef",
    },
]


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion from seed value to appropriate Python/DB value."""
    if raw == "" or raw is None:
        return None

    t = col.type

    if isinstance(t, sa.Boolean):
        if isinstance(raw, str):
            v = raw.strip().lower()
            if v in ("true", "t", "1", "yes", "y"):
                return True
            if v in ("false", "f", "0", "no", "n"):
                return False
            log.warning(
                "Invalid boolean for %s.%s: %r", TABLE_NAME, col.name, raw
            )
            return None
        return bool(raw)

    return raw


def upgrade() -> None:
    """Insert inline seed data for consequences."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(TABLE_NAME):
        log.warning("Table %s does not exist; skipping seed", TABLE_NAME)
        return

    metadata = sa.MetaData()
    table = sa.Table(TABLE_NAME, metadata, autoload_with=bind)

    if not SEED_ROWS:
        log.info("No inline seed rows defined for %s; skipping", TABLE_NAME)
        return

    inserted = 0
    for raw_row in SEED_ROWS:
        row = {}

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

    log.info("Inserted %s inline rows into %s", inserted, TABLE_NAME)


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
