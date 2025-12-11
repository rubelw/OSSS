from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0075"
down_revision = "0074"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "buildings"

# Inline seed data for buildings
SEED_ROWS = [
    {
        "facility_id": "8b3a1f79-8f2e-4e3e-9bb8-32d4c7aa1101",
        "name": "DCG High School Main Building",
        "code": "HS-MAIN",
        "year_built": 2013,
        "floors_count": 1,
        "gross_sqft": 220000,
        "use_type": "academic",
        "address": "1600 8th St, Grimes, IA 50111",
        "attributes": {},
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
        "id": "2fcc53b4-7367-5852-9afb-ffdecafad618",
    },
    {
        "facility_id": "c92f3d44-0c76-4eab-8c8c-97c369fb4a91",
        "name": "DCG High School Activities Complex",
        "code": "HS-ACT",
        "year_built": 2014,
        "floors_count": 1,
        "gross_sqft": 75000,
        "use_type": "athletic",
        "address": "2100 NE Beaverbrooke Blvd, Grimes, IA 50111",
        "attributes": {},
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
        "id": "ac05fede-8a71-5021-8aac-111b81fe9040",
    },
    {
        "facility_id": "3fe8b0b5-d22c-4e7b-af46-b08928285c44",
        "name": "DCG High School Transportation Garage",
        "code": "HS-GAR",
        "year_built": 2012,
        "floors_count": 1,
        "gross_sqft": 25000,
        "use_type": "transportation",
        "address": "1400 NE Destination Dr, Grimes, IA 50111",
        "attributes": {},
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
        "id": "01d40763-429e-585e-9337-610bb77f6d88",
    },
    {
        "facility_id": "4ad66d0c-bbcc-4a7a-97fe-ff12cf37eb2f",
        "name": "DCG High School Baseball & Softball Complex",
        "code": "HS-BSB",
        "year_built": 2015,
        "floors_count": 1,
        "gross_sqft": 15000,
        "use_type": "athletic",
        "address": "2100 NE Beaverbrooke Blvd, Grimes, IA 50111",
        "attributes": {},
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
        "id": "6f71271f-fe6d-5aff-a786-3cd7f6f506a4",
    },
    {
        "facility_id": "1e87bfc8-be83-4bfa-a93b-973df8a2d6cd",
        "name": "DCG High School Fine Arts Wing",
        "code": "HS-ART",
        "year_built": 2016,
        "floors_count": 1,
        "gross_sqft": 80000,
        "use_type": "arts",
        "address": "1600 8th St, Grimes, IA 50111",
        "attributes": {},
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
        "id": "750af9d1-af56-5eab-b90b-97eec33808fa",
    },
    {
        "facility_id": "91f25e67-d4dd-4fc9-a172-fef6d51027db",
        "name": "DCG Middle School",
        "code": "MS-MAIN",
        "year_built": 2016,
        "floors_count": 1,
        "gross_sqft": 80000,
        "use_type": "arts",
        "address": "1600 8th St, Grimes, IA 50111",
        "attributes": {},
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
        "id": "750af9d1-af56-5eab-b90b-97eec33801fa",
    },
    {
        "facility_id": "e4bcaaef-a3c0-4d73-adf7-38bb0ed012ef",
        "name": "South Prairie Elementary School",
        "code": "SP-MAIN",
        "year_built": 2016,
        "floors_count": 1,
        "gross_sqft": 80000,
        "use_type": "arts",
        "address": "1600 8th St, Grimes, IA 50111",
        "attributes": {},
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
        "id": "750af9d1-af56-5eab-b90b-97eec33802fa",
    },
    {
        "facility_id": "bd26aa8b-49cb-4b4c-8a36-7c4afbb89c52",
        "name": "Heritage Elementary School",
        "code": "H-MAIN",
        "year_built": 2016,
        "floors_count": 1,
        "gross_sqft": 80000,
        "use_type": "arts",
        "address": "1600 8th St, Grimes, IA 50111",
        "attributes": {},
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
        "id": "750af9d1-af56-5eab-b90b-97eec33803fa",
    },
    {
        "facility_id": "aa94cb07-ec40-45cc-9ed0-e6e3ad2bb93d",
        "name": "North Ridge Elementary School",
        "code": "NR-MAIN",
        "year_built": 2016,
        "floors_count": 1,
        "gross_sqft": 80000,
        "use_type": "arts",
        "address": "1600 8th St, Grimes, IA 50111",
        "attributes": {},
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
        "id": "750af9d1-af56-5eab-b90b-97eec33804fa",
    }
]


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion from CSV/Python value to appropriate DB-bound value."""
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

    # Otherwise, pass raw through and let DB cast (e.g., timestamps, ints)
    return raw


def upgrade() -> None:
    """Load seed data for buildings from inline SEED_ROWS.

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

    if not SEED_ROWS:
        log.info("No seed rows defined for %s", TABLE_NAME)
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

    log.info("Inserted %s rows into %s (inline seed)", inserted, TABLE_NAME)


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
