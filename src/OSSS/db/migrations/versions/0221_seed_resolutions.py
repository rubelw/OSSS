from __future__ import annotations

import csv  # kept for consistency with other migrations, even though not used now
import logging
import os

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0221"
down_revision = "0220"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "resolutions"
CSV_FILE = None  # now seeding from inline data instead of CSV

# Columns:
# meeting_id, title, summary, effective_date, status, created_at, updated_at, id
SEED_ROWS = [
    {
        "meeting_id": "89ab8c9b-8c20-5b36-95db-e4e7e0a5e3b4",
        "title": "Adoption of 2024 Board Meeting Calendar",
        "summary": (
            "A resolution approving the regular board meeting calendar for calendar year 2024, "
            "including scheduled dates, times, and locations for monthly meetings and work sessions. "
            "The superintendent is directed to publish the calendar on the district website and "
            "provide notice to local media outlets."
        ),
        "effective_date": "2024-01-02",
        "status": "adopted",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
        "id": "95bc3bae-f894-55c8-acf7-e831ffe07226",
    },
    {
        "meeting_id": "89ab8c9b-8c20-5b36-95db-e4e7e0a5e3b4",
        "title": "Approval of FY24 Budget Amendment",
        "summary": (
            "A resolution amending the FY24 certified budget to reflect updated enrollment, "
            "special education, and activities fund projections. The amendment does not exceed "
            "the district’s authorized spending authority and will be filed with the Department of Education."
        ),
        "effective_date": "2024-01-03",
        "status": "adopted",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
        "id": "16e812b4-53ca-5384-a7b8-a9605b25fed4",
    },
    {
        "meeting_id": "89ab8c9b-8c20-5b36-95db-e4e7e0a5e3b4",
        "title": "Authorization of Capital Projects Fund Transfers",
        "summary": (
            "A resolution authorizing the transfer of designated SAVE and PPEL revenues to the "
            "capital projects fund for the high school athletic complex and classroom renovation projects. "
            "The chief financial officer is directed to complete all required internal and state reporting."
        ),
        "effective_date": "2024-01-04",
        "status": "adopted",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
        "id": "01e5069b-3a87-566f-977c-517b6de0bc0d",
    },
    {
        "meeting_id": "89ab8c9b-8c20-5b36-95db-e4e7e0a5e3b4",
        "title": "First Reading of Board Policy Revisions – Series 500 (Students)",
        "summary": (
            "A resolution acknowledging the first reading of policy revisions in Series 500 related to "
            "attendance, discipline, and student activities eligibility. The proposed changes align district "
            "policy with updated state code and IASB recommendations. Final action will be considered at a "
            "subsequent regular meeting."
        ),
        "effective_date": "2024-01-05",
        "status": "tabled",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
        "id": "d782b812-0706-50cf-8a3b-b3f512145b25",
    },
    {
        "meeting_id": "89ab8c9b-8c20-5b36-95db-e4e7e0a5e3b4",
        "title": "Creation of Activities Facilities Planning Committee",
        "summary": (
            "A resolution establishing an Activities Facilities Planning Committee composed of board members, "
            "administrators, coaches, and community representatives. The committee is charged with developing "
            "recommendations on long-term facility needs, financing options, and community engagement related "
            "to athletics and co-curricular spaces."
        ),
        "effective_date": "2024-01-06",
        "status": "referred",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
        "id": "7135e12f-3648-5534-9477-f8f6795a8533",
    },
]


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion from inline seed values to appropriate Python/DB values."""
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

    # Otherwise, pass raw through and let DB or dialect cast (UUID, date, timestamptz, text, etc.)
    return raw


def upgrade() -> None:
    """Load seed data for resolutions from inline SEED_ROWS (no CSV)."""
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

        # Explicit nested transaction (SAVEPOINT) so a bad row doesn't kill the migration
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
