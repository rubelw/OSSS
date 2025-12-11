from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0093"
down_revision = "0092"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "teams"

# Inline seed data for teams
# Columns: sport_id, name, mascot, created_at, updated_at, season_id, school_id, id
SEED_ROWS = [
    {
        "sport_id": "93200509-52cc-4e08-9732-e987248637cd",
        "name": "DCG Varsity Football",
        "mascot": "Mustangs",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
        "season_id": "c39ad8bc-6fea-4025-9a5f-d1887a04fe6c",
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "id": "ee268bc5-47ec-59b2-b5bb-00492928ca1f",
    },
    {
        "sport_id": "ed683bdf-bb90-496b-8358-8aa6a23fe671",
        "name": "DCG Varsity Volleyball",
        "mascot": "Mustangs",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
        "season_id": "c39ad8bc-6fea-4025-9a5f-d1887a04fe6c",
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "id": "adad662e-9253-58d2-8da8-d9c622dfb956",
    },
    {
        "sport_id": "89d5b3f6-5de7-4cf7-9755-09f7c86f09f4",
        "name": "DCG Boys Basketball",
        "mascot": "Mustangs",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
        "season_id": "cc1999cc-7e3e-48de-8d4e-eba85196f3e0",
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "id": "b8a1ffbe-569a-537b-8810-0a2adf30b845",
    },
    {
        "sport_id": "2cc9830c-d75a-41be-884f-cfcd87b8fa5a",
        "name": "DCG Middle School Track & Field",
        "mascot": "Mustangs",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
        "season_id": "cc1999cc-7e3e-48de-8d4e-eba85196f3e0",
        "school_id": "119caaef-ef97-5364-b179-388e108bd40d",
        "id": "94a1040e-de5d-58bf-b3d5-3d02fedc5dc8",
    },
    {
        "sport_id": "5da02e28-1b97-4cc3-a781-ef2019c41e29",
        "name": "DCG Middle School Baseball",
        "mascot": "Mustangs",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
        "season_id": "cc1999cc-7e3e-48de-8d4e-eba85196f3e0",
        "school_id": "119caaef-ef97-5364-b179-388e108bd40d",
        "id": "01eead7b-0e60-504b-94b0-e90c97b3e8c1",
    },
]


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion from inline value to appropriate Python/DB value."""
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

    # Otherwise, let DB/SQLAlchemy cast (UUID, timestamptz, etc.)
    return raw


def upgrade() -> None:
    """Load seed data for teams from inline SEED_ROWS with per-row SAVEPOINTs."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(TABLE_NAME):
        log.warning("Table %s does not exist; skipping seed", TABLE_NAME)
        return

    if not SEED_ROWS:
        log.info("No inline seed rows defined for %s", TABLE_NAME)
        return

    metadata = sa.MetaData()
    table = sa.Table(TABLE_NAME, metadata, autoload_with=bind)

    inserted = 0
    for raw_row in SEED_ROWS:
        row: dict[str, object] = {}

        # Only include columns that actually exist on the table
        for col in table.columns:
            if col.name not in raw_row:
                continue
            raw_val = raw_row[col.name]
            row[col.name] = _coerce_value(col, raw_val)

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
