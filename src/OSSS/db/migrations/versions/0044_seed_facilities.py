from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0044"
down_revision = "0043"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "facilities"

# Inline seed rows matching the Facility model
SEED_ROWS = [
    # ----- DCG High School -----
    {
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "name": "DCG High School Main Building",
        "code": "HS-MAIN",
        "address": "1600 8th St, Grimes, IA 50111",
        "attributes": {},
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
        "id": "8b3a1f79-8f2e-4e3e-9bb8-32d4c7aa1101",
    },
    {
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "name": "DCG High School Activities Complex",
        "code": "HS-ACT",
        "address": "2100 NE Beaverbrooke Blvd, Grimes, IA 50111",
        "attributes": {"type": "athletic"},
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
        "id": "c92f3d44-0c76-4eab-8c8c-97c369fb4a91",
    },
    {
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "name": "DCG High School Transportation Garage",
        "code": "HS-GAR",
        "address": "1400 NE Destination Dr, Grimes, IA 50111",
        "attributes": {"type": "transportation"},
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
        "id": "3fe8b0b5-d22c-4e7b-af46-b08928285c44",
    },
    {
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "name": "DCG High School Baseball/Softball Complex",
        "code": "HS-BSB",
        "address": "2100 NE Beaverbrooke Blvd, Grimes, IA 50111",
        "attributes": {"type": "athletic"},
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
        "id": "4ad66d0c-bbcc-4a7a-97fe-ff12cf37eb2f",
    },
    {
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "name": "DCG High School Fine Arts Wing",
        "code": "HS-ART",
        "address": "1600 8th St, Grimes, IA 50111",
        "attributes": {"type": "arts"},
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
        "id": "1e87bfc8-be83-4bfa-a93b-973df8a2d6cd",
    },

    # ----- DCG Middle School -----
    {
        "school_id": "119caaef-ef97-5364-b179-388e108bd40d",
        "name": "DCG Middle School Main Building",
        "code": "MS-MAIN",
        "address": "1400 Vine St, Dallas Center, IA 50063",
        "attributes": {},
        "created_at": "2024-01-01T01:15:00Z",
        "updated_at": "2024-01-01T01:15:00Z",
        "id": "91f25e67-d4dd-4fc9-a172-fef6d51027db",
    },
    {
        "school_id": "119caaef-ef97-5364-b179-388e108bd40d",
        "name": "DCG Middle School Gymnasium",
        "code": "MS-GYM",
        "address": "1400 Vine St, Dallas Center, IA 50063",
        "attributes": {"type": "athletic"},
        "created_at": "2024-01-01T02:15:00Z",
        "updated_at": "2024-01-01T02:15:00Z",
        "id": "3a355448-ef69-4bdc-8388-4b7150b2a731",
    },
    {
        "school_id": "119caaef-ef97-5364-b179-388e108bd40d",
        "name": "DCG Middle School Annex",
        "code": "MS-ANNEX",
        "address": "1410 Vine St, Dallas Center, IA 50063",
        "attributes": {},
        "created_at": "2024-01-01T03:15:00Z",
        "updated_at": "2024-01-01T03:15:00Z",
        "id": "2f03f9fb-16cf-4bb7-a1f1-2522c1c7a422",
    },
    {
        "school_id": "119caaef-ef97-5364-b179-388e108bd40d",
        "name": "DCG Middle School Cafeteria",
        "code": "MS-CAF",
        "address": "1400 Vine St, Dallas Center, IA 50063",
        "attributes": {},
        "created_at": "2024-01-01T04:15:00Z",
        "updated_at": "2024-01-01T04:15:00Z",
        "id": "5c11f34f-d0aa-4c11-bd49-f641a5325fa6",
    },
    {
        "school_id": "119caaef-ef97-5364-b179-388e108bd40d",
        "name": "DCG Middle School Auditorium",
        "code": "MS-AUD",
        "address": "1400 Vine St, Dallas Center, IA 50063",
        "attributes": {"type": "arts"},
        "created_at": "2024-01-01T05:15:00Z",
        "updated_at": "2024-01-01T05:15:00Z",
        "id": "6a0f6bba-bfee-4686-a093-09a0ae502c53",
    },

    # ----- South Prairie Elementary -----
    {
        "school_id": "b122fcb4-2864-593c-9b05-2188ef296db4",
        "name": "South Prairie Elementary Main Building",
        "code": "SP-MAIN",
        "address": "700 SE 37th St, Grimes, IA 50111",
        "attributes": {},
        "created_at": "2024-01-01T01:30:00Z",
        "updated_at": "2024-01-01T01:30:00Z",
        "id": "e4bcaaef-a3c0-4d73-adf7-38bb0ed012ef",
    },
    {
        "school_id": "b122fcb4-2864-593c-9b05-2188ef296db4",
        "name": "South Prairie Playground",
        "code": "SP-PLAY",
        "address": "700 SE 37th St, Grimes, IA 50111",
        "attributes": {"type": "recreation"},
        "created_at": "2024-01-01T02:30:00Z",
        "updated_at": "2024-01-01T02:30:00Z",
        "id": "cbafad75-0cc2-4ba6-bd02-e8507d8f9e15",
    },
    {
        "school_id": "b122fcb4-2864-593c-9b05-2188ef296db4",
        "name": "South Prairie Cafeteria",
        "code": "SP-CAF",
        "address": "700 SE 37th St, Grimes, IA 50111",
        "attributes": {},
        "created_at": "2024-01-01T03:30:00Z",
        "updated_at": "2024-01-01T03:30:00Z",
        "id": "41aac64c-1c10-47cb-8d8a-df8c17dbfad7",
    },
    {
        "school_id": "b122fcb4-2864-593c-9b05-2188ef296db4",
        "name": "South Prairie Gymnasium",
        "code": "SP-GYM",
        "address": "700 SE 37th St, Grimes, IA 50111",
        "attributes": {"type": "athletic"},
        "created_at": "2024-01-01T04:30:00Z",
        "updated_at": "2024-01-01T04:30:00Z",
        "id": "8fa669e4-bd81-4e63-b88a-32a35b9c876c",
    },
    {
        "school_id": "b122fcb4-2864-593c-9b05-2188ef296db4",
        "name": "South Prairie Music Room",
        "code": "SP-MUSIC",
        "address": "700 SE 37th St, Grimes, IA 50111",
        "attributes": {"type": "arts"},
        "created_at": "2024-01-01T05:30:00Z",
        "updated_at": "2024-01-01T05:30:00Z",
        "id": "90c9229d-1744-4635-bd53-d65ccbe3a70a",
    },

    # ----- Heritage Elementary -----
    {
        "school_id": "df4b1423-d755-5c7f-a0ba-6908de77f61b",
        "name": "Heritage Elementary Main Building",
        "code": "HE-MAIN",
        "address": "5050 NW 2nd Ave, Des Moines, IA 50313",
        "attributes": {},
        "created_at": "2024-01-01T01:45:00Z",
        "updated_at": "2024-01-01T01:45:00Z",
        "id": "bd26aa8b-49cb-4b4c-8a36-7c4afbb89c52",
    },
    {
        "school_id": "df4b1423-d755-5c7f-a0ba-6908de77f61b",
        "name": "Heritage Playground",
        "code": "HE-PLAY",
        "address": "5050 NW 2nd Ave, Des Moines, IA 50313",
        "attributes": {"type": "recreation"},
        "created_at": "2024-01-01T02:45:00Z",
        "updated_at": "2024-01-01T02:45:00Z",
        "id": "29dfb488-66f0-4dd4-b1e6-0d3b33211147",
    },
    {
        "school_id": "df4b1423-d755-5c7f-a0ba-6908de77f61b",
        "name": "Heritage Gymnasium",
        "code": "HE-GYM",
        "address": "5050 NW 2nd Ave, Des Moines, IA 50313",
        "attributes": {"type": "athletic"},
        "created_at": "2024-01-01T03:45:00Z",
        "updated_at": "2024-01-01T03:45:00Z",
        "id": "4fa52e33-90e8-4da1-a4ce-3cf8912fe019",
    },
    {
        "school_id": "df4b1423-d755-5c7f-a0ba-6908de77f61b",
        "name": "Heritage Music Room",
        "code": "HE-MUSIC",
        "address": "5050 NW 2nd Ave, Des Moines, IA 50313",
        "attributes": {"type": "arts"},
        "created_at": "2024-01-01T04:45:00Z",
        "updated_at": "2024-01-01T04:45:00Z",
        "id": "ecc5b005-07d3-42ae-bd61-14b7f0bf548c",
    },
    {
        "school_id": "df4b1423-d755-5c7f-a0ba-6908de77f61b",
        "name": "Heritage STEM Lab",
        "code": "HE-STEM",
        "address": "5050 NW 2nd Ave, Des Moines, IA 50313",
        "attributes": {"type": "stem"},
        "created_at": "2024-01-01T05:45:00Z",
        "updated_at": "2024-01-01T05:45:00Z",
        "id": "7e2f6ee7-d17e-40f4-8ad0-1c0ee228dab3",
    },

    # ----- North Ridge Elementary -----
    {
        "school_id": "634b8058-d620-5a5c-86b5-c0794d3a3b73",
        "name": "North Ridge Elementary Main Building",
        "code": "NRE-MAIN",
        "address": "400 NW 27th St, Grimes, IA 50111",
        "attributes": {},
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
        "id": "aa94cb07-ec40-45cc-9ed0-e6e3ad2bb93d",
    },
    {
        "school_id": "634b8058-d620-5a5c-86b5-c0794d3a3b73",
        "name": "North Ridge Playground",
        "code": "NRE-PLAY",
        "address": "400 NW 27th St, Grimes, IA 50111",
        "attributes": {"type": "recreation"},
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
        "id": "2f7a499b-1751-4779-b991-4fb3a18b30bb",
    },
    {
        "school_id": "634b8058-d620-5a5c-86b5-c0794d3a3b73",
        "name": "North Ridge Gymnasium",
        "code": "NRE-GYM",
        "address": "400 NW 27th St, Grimes, IA 50111",
        "attributes": {"type": "athletic"},
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
        "id": "9cbf4ef6-c029-48f8-9c27-ca8083d3f9d1",
    },
    {
        "school_id": "634b8058-d620-5a5c-86b5-c0794d3a3b73",
        "name": "North Ridge Library",
        "code": "NRE-LIB",
        "address": "400 NW 27th St, Grimes, IA 50111",
        "attributes": {},
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
        "id": "d17cf9b3-8161-47c5-9b13-3bd4a2f2d5de",
    },
    {
        "school_id": "634b8058-d620-5a5c-86b5-c0794d3a3b73",
        "name": "North Ridge STEM Lab",
        "code": "NRE-STEM",
        "address": "400 NW 27th St, Grimes, IA 50111",
        "attributes": {"type": "stem"},
        "created_at": "2024-01-01T06:00:00Z",
        "updated_at": "2024-01-01T06:00:00Z",
        "id": "362fd098-01dd-417d-a4e2-a1ebcc91fb93",
    },
]


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion from Python value to appropriate DB-bound value."""
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

    # For JSON, we assume raw is already a dict/list/primitive and let SA handle it
    # For everything else, pass through and let DB cast (timestamps, UUIDs, etc.)
    return raw


def upgrade() -> None:
    """Load seed data for facilities from inline SEED_ROWS.

    Each row is inserted inside an explicit nested transaction (SAVEPOINT)
    so a failing row won't abort the whole migration transaction.
    """
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(TABLE_NAME):
        log.warning("Table %s does not exist; skipping seed", TABLE_NAME)
        return

    if not SEED_ROWS:
        log.info("No seed rows defined for %s; skipping", TABLE_NAME)
        return

    metadata = sa.MetaData()
    table = sa.Table(TABLE_NAME, metadata, autoload_with=bind)

    inserted = 0
    for raw_row in SEED_ROWS:
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

    log.info("Inserted %s rows into %s from inline seed data", inserted, TABLE_NAME)


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
