from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0047"
down_revision = "0046"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "departments"

SEED_ROWS = [
    # DCG High School
    {
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "name": "High School English Department",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
        "id": "c3ce8fe1-2cf5-4cff-86a5-a9933ea34428",
    },
    {
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "name": "High School Mathematics Department",
        "created_at": "2024-01-01T01:10:00Z",
        "updated_at": "2024-01-01T01:10:00Z",
        "id": "77f707ec-6000-4305-8312-966519dbff3a",
    },
    {
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "name": "High School Science Department",
        "created_at": "2024-01-01T01:20:00Z",
        "updated_at": "2024-01-01T01:20:00Z",
        "id": "9761e232-9e56-46ec-bfd8-45c67760ba0a",
    },
    {
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "name": "High School Social Studies Department",
        "created_at": "2024-01-01T01:30:00Z",
        "updated_at": "2024-01-01T01:30:00Z",
        "id": "67c834dc-8e58-4f77-8a0e-7cb1f903861a",
    },
    {
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "name": "High School Fine Arts Department",
        "created_at": "2024-01-01T01:40:00Z",
        "updated_at": "2024-01-01T01:40:00Z",
        "id": "af370a73-55c2-4715-a137-8eda4835239c",
    },
    {
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "name": "High School Administration",
        "created_at": "2024-01-01T01:50:00Z",
        "updated_at": "2024-01-01T01:50:00Z",
        "id": "c4c7b5f4-3a3d-4d0c-9480-1c37f6f3c111",
    },

    # DCG Middle School
    {
        "school_id": "119caaef-ef97-5364-b179-388e108bd40d",
        "name": "Middle School English/Language Arts Department",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
        "id": "2eb8bcbc-0718-4fca-8f67-3563f3258e76",
    },
    {
        "school_id": "119caaef-ef97-5364-b179-388e108bd40d",
        "name": "Middle School Mathematics Department",
        "created_at": "2024-01-01T02:10:00Z",
        "updated_at": "2024-01-01T02:10:00Z",
        "id": "7a8cf456-3192-4895-b8ec-f7d53cbd9801",
    },
    {
        "school_id": "119caaef-ef97-5364-b179-388e108bd40d",
        "name": "Middle School Science Department",
        "created_at": "2024-01-01T02:20:00Z",
        "updated_at": "2024-01-01T02:20:00Z",
        "id": "8e353e8c-b174-45bc-b3e7-7dbee1a13310",
    },
    {
        "school_id": "119caaef-ef97-5364-b179-388e108bd40d",
        "name": "Middle School Social Studies Department",
        "created_at": "2024-01-01T02:30:00Z",
        "updated_at": "2024-01-01T02:30:00Z",
        "id": "6e0f29ed-7bac-483f-a7ce-dfabdfc096dd",
    },
    {
        "school_id": "119caaef-ef97-5364-b179-388e108bd40d",
        "name": "Middle School Specials (Art/Music/PE)",
        "created_at": "2024-01-01T02:40:00Z",
        "updated_at": "2024-01-01T02:40:00Z",
        "id": "79fc1417-f988-46e5-99cf-ae9aba5c09e2",
    },
    {
        "school_id": "119caaef-ef97-5364-b179-388e108bd40d",
        "name": "Middle School Administration",
        "created_at": "2024-01-01T02:50:00Z",
        "updated_at": "2024-01-01T02:50:00Z",
        "id": "3b8c6ed1-0fd7-4ab5-9e2d-2fcac0f9f222",
    },

    # South Prairie Elementary
    {
        "school_id": "b122fcb4-2864-593c-9b05-2188ef296db4",
        "name": "South Prairie Classroom Teachers",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
        "id": "4e62ed1f-5acf-494d-b9a2-3cc4fe950cf0",
    },
    {
        "school_id": "b122fcb4-2864-593c-9b05-2188ef296db4",
        "name": "South Prairie Special Education",
        "created_at": "2024-01-01T03:10:00Z",
        "updated_at": "2024-01-01T03:10:00Z",
        "id": "cdead00b-74fd-4760-bb49-f2b36fe46964",
    },
    {
        "school_id": "b122fcb4-2864-593c-9b05-2188ef296db4",
        "name": "South Prairie Specials (Art/Music/PE)",
        "created_at": "2024-01-01T03:20:00Z",
        "updated_at": "2024-01-01T03:20:00Z",
        "id": "687b59dd-7f8e-4d5b-8061-359dc8b86ecc",
    },
    {
        "school_id": "b122fcb4-2864-593c-9b05-2188ef296db4",
        "name": "South Prairie Intervention & Reading Support",
        "created_at": "2024-01-01T03:30:00Z",
        "updated_at": "2024-01-01T03:30:00Z",
        "id": "408886ef-c8e2-4199-86be-089555f69db5",
    },
    {
        "school_id": "b122fcb4-2864-593c-9b05-2188ef296db4",
        "name": "South Prairie Student Services (Counseling/Nursing)",
        "created_at": "2024-01-01T03:40:00Z",
        "updated_at": "2024-01-01T03:40:00Z",
        "id": "1de20956-ec18-4804-b30f-4ad9eb7e0827",
    },
    {
        "school_id": "b122fcb4-2864-593c-9b05-2188ef296db4",
        "name": "South Prairie Administration",
        "created_at": "2024-01-01T03:50:00Z",
        "updated_at": "2024-01-01T03:50:00Z",
        "id": "5f6a1f87-8d5c-4f2a-bf9c-3d0e8f6e7333",
    },

    # Heritage Elementary
    {
        "school_id": "df4b1423-d755-5c7f-a0ba-6908de77f61b",
        "name": "Heritage Classroom Teachers",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
        "id": "d86cff59-6ded-4435-9f58-327934f47e59",
    },
    {
        "school_id": "df4b1423-d755-5c7f-a0ba-6908de77f61b",
        "name": "Heritage Special Education",
        "created_at": "2024-01-01T04:10:00Z",
        "updated_at": "2024-01-01T04:10:00Z",
        "id": "86c4adde-e5bd-4c43-9c78-9fff47800319",
    },
    {
        "school_id": "df4b1423-d755-5c7f-a0ba-6908de77f61b",
        "name": "Heritage Specials (Art/Music/PE)",
        "created_at": "2024-01-01T04:20:00Z",
        "updated_at": "2024-01-01T04:20:00Z",
        "id": "97175810-7874-4bbc-b7a6-023fe04d5829",
    },
    {
        "school_id": "df4b1423-d755-5c7f-a0ba-6908de77f61b",
        "name": "Heritage Intervention & Reading Support",
        "created_at": "2024-01-01T04:30:00Z",
        "updated_at": "2024-01-01T04:30:00Z",
        "id": "1b1f7a10-d786-4fd5-99af-4229eb8283fb",
    },
    {
        "school_id": "df4b1423-d755-5c7f-a0ba-6908de77f61b",
        "name": "Heritage Student Services (Counseling/Nursing)",
        "created_at": "2024-01-01T04:40:00Z",
        "updated_at": "2024-01-01T04:40:00Z",
        "id": "cac64beb-8960-458d-b247-da7c86c07356",
    },
    {
        "school_id": "df4b1423-d755-5c7f-a0ba-6908de77f61b",
        "name": "Heritage Administration",
        "created_at": "2024-01-01T04:50:00Z",
        "updated_at": "2024-01-01T04:50:00Z",
        "id": "6c2f0c84-0e7f-4f8d-9c5b-9b5e0d4e8444",
    },

    # North Ridge Elementary
    {
        "school_id": "634b8058-d620-5a5c-86b5-c0794d3a3b73",
        "name": "North Ridge Classroom Teachers",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
        "id": "97d4c03c-2f34-4079-a8a9-ad33ea1b3be7",
    },
    {
        "school_id": "634b8058-d620-5a5c-86b5-c0794d3a3b73",
        "name": "North Ridge Special Education",
        "created_at": "2024-01-01T05:10:00Z",
        "updated_at": "2024-01-01T05:10:00Z",
        "id": "c3ecfa17-7719-4778-ac6f-0ec370460cf8",
    },
    {
        "school_id": "634b8058-d620-5a5c-86b5-c0794d3a3b73",
        "name": "North Ridge Specials (Art/Music/PE)",
        "created_at": "2024-01-01T05:20:00Z",
        "updated_at": "2024-01-01T05:20:00Z",
        "id": "9ed3b88b-fa03-4f5a-b3be-fcf789fdb977",
    },
    {
        "school_id": "634b8058-d620-5a5c-86b5-c0794d3a3b73",
        "name": "North Ridge Intervention & Reading Support",
        "created_at": "2024-01-01T05:30:00Z",
        "updated_at": "2024-01-01T05:30:00Z",
        "id": "4718e7cc-ad33-400c-9e4b-f1c0fdfe220d",
    },
    {
        "school_id": "634b8058-d620-5a5c-86b5-c0794d3a3b73",
        "name": "North Ridge Student Services (Counseling/Nursing)",
        "created_at": "2024-01-01T05:40:00Z",
        "updated_at": "2024-01-01T05:40:00Z",
        "id": "d17dc1fb-61ab-4f68-8ee0-149f71580bb2",
    },
    {
        "school_id": "634b8058-d620-5a5c-86b5-c0794d3a3b73",
        "name": "North Ridge Administration",
        "created_at": "2024-01-01T05:50:00Z",
        "updated_at": "2024-01-01T05:50:00Z",
        "id": "7d4a3b29-5c2f-4ef0-a7f0-2f4c7a6d9555",
    },
]


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion from inline value to appropriate DB-bound value."""
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

    # Otherwise, pass raw through and let DB cast (timestamps, etc.)
    return raw


def upgrade() -> None:
    """Load seed data for departments from inline SEED_ROWS.

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
            raw_val = None

            # Direct match if present
            if col.name in raw_row:
                raw_val = raw_row[col.name]
            else:
                # Let created_at/updated_at or other server-default columns be omitted
                continue

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
