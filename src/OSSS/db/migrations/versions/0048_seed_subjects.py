from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0048"
down_revision = "0047"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "subjects"

# Inline seed data for subjects
SEED_ROWS = [
    # High School – English
    {
        "department_id": "c3ce8fe1-2cf5-4cff-86a5-a9933ea34428",
        "name": "English 9",
        "code": "ENG9",
        "created_at": "2024-01-02T01:00:00Z",
        "updated_at": "2024-01-02T01:00:00Z",
        "id": "01010101-0101-4101-8101-010101010101",
    },
    {
        "department_id": "c3ce8fe1-2cf5-4cff-86a5-a9933ea34428",
        "name": "English 10",
        "code": "ENG10",
        "created_at": "2024-01-02T01:10:00Z",
        "updated_at": "2024-01-02T01:10:00Z",
        "id": "02020202-0202-4202-8202-020202020202",
    },

    # High School – Math
    {
        "department_id": "77f707ec-6000-4305-8312-966519dbff3a",
        "name": "Algebra I",
        "code": "ALG1_HS",
        "created_at": "2024-01-02T01:20:00Z",
        "updated_at": "2024-01-02T01:20:00Z",
        "id": "03030303-0303-4303-8303-030303030303",
    },
    {
        "department_id": "77f707ec-6000-4305-8312-966519dbff3a",
        "name": "Geometry",
        "code": "GEOM_HS",
        "created_at": "2024-01-02T01:30:00Z",
        "updated_at": "2024-01-02T01:30:00Z",
        "id": "04040404-0404-4404-8404-040404040404",
    },

    # High School – Science
    {
        "department_id": "9761e232-9e56-46ec-bfd8-45c67760ba0a",
        "name": "Biology",
        "code": "BIO_HS",
        "created_at": "2024-01-02T01:40:00Z",
        "updated_at": "2024-01-02T01:40:00Z",
        "id": "05050505-0505-4505-8505-050505050505",
    },
    {
        "department_id": "9761e232-9e56-46ec-bfd8-45c67760ba0a",
        "name": "Chemistry",
        "code": "CHEM_HS",
        "created_at": "2024-01-02T01:50:00Z",
        "updated_at": "2024-01-02T01:50:00Z",
        "id": "06060606-0606-4606-8606-060606060606",
    },

    # High School – Social Studies
    {
        "department_id": "67c834dc-8e58-4f77-8a0e-7cb1f903861a",
        "name": "U.S. History",
        "code": "USHIST_HS",
        "created_at": "2024-01-02T02:00:00Z",
        "updated_at": "2024-01-02T02:00:00Z",
        "id": "07070707-0707-4707-8707-070707070707",
    },
    {
        "department_id": "67c834dc-8e58-4f77-8a0e-7cb1f903861a",
        "name": "World History",
        "code": "WORLD_HS",
        "created_at": "2024-01-02T02:10:00Z",
        "updated_at": "2024-01-02T02:10:00Z",
        "id": "08080808-0808-4808-8808-080808080808",
    },

    # High School – Fine Arts
    {
        "department_id": "af370a73-55c2-4715-a137-8eda4835239c",
        "name": "Concert Band",
        "code": "CBAND_HS",
        "created_at": "2024-01-02T02:20:00Z",
        "updated_at": "2024-01-02T02:20:00Z",
        "id": "09090909-0909-4909-8909-090909090909",
    },
    {
        "department_id": "af370a73-55c2-4715-a137-8eda4835239c",
        "name": "Concert Choir",
        "code": "CCHOIR_HS",
        "created_at": "2024-01-02T02:30:00Z",
        "updated_at": "2024-01-02T02:30:00Z",
        "id": "0a0a0a0a-0a0a-4a0a-8a0a-0a0a0a0a0a0a",
    },

    # Middle School
    {
        "department_id": "2eb8bcbc-0718-4fca-8f67-3563f3258e76",
        "name": "6th Grade Language Arts",
        "code": "ELA6_MS",
        "created_at": "2024-01-02T03:00:00Z",
        "updated_at": "2024-01-02T03:00:00Z",
        "id": "0b0b0b0b-0b0b-4b0b-8b0b-0b0b0b0b0b0b",
    },
    {
        "department_id": "7a8cf456-3192-4895-b8ec-f7d53cbd9801",
        "name": "7th Grade Mathematics",
        "code": "MATH7_MS",
        "created_at": "2024-01-02T03:10:00Z",
        "updated_at": "2024-01-02T03:10:00Z",
        "id": "0c0c0c0c-0c0c-4c0c-8c0c-0c0c0c0c0c0c",
    },
    {
        "department_id": "8e353e8c-b174-45bc-b3e7-7dbee1a13310",
        "name": "8th Grade Science",
        "code": "SCI8_MS",
        "created_at": "2024-01-02T03:20:00Z",
        "updated_at": "2024-01-02T03:20:00Z",
        "id": "0d0d0d0d-0d0d-4d0d-8d0d-0d0d0d0d0d0d",
    },
    {
        "department_id": "6e0f29ed-7bac-483f-a7ce-dfabdfc096dd",
        "name": "6th Grade Social Studies",
        "code": "SS6_MS",
        "created_at": "2024-01-02T03:30:00Z",
        "updated_at": "2024-01-02T03:30:00Z",
        "id": "0e0e0e0e-0e0e-4e0e-8e0e-0e0e0e0e0e0e",
    },
    {
        "department_id": "79fc1417-f988-46e5-99cf-ae9aba5c09e2",
        "name": "Middle School Art",
        "code": "ART_MS",
        "created_at": "2024-01-02T03:40:00Z",
        "updated_at": "2024-01-02T03:40:00Z",
        "id": "0f0f0f0f-0f0f-4f0f-8f0f-0f0f0f0f0f0f",
    },

    # South Prairie
    {
        "department_id": "4e62ed1f-5acf-494d-b9a2-3cc4fe950cf0",
        "name": "South Prairie Reading",
        "code": "READ_SP",
        "created_at": "2024-01-02T04:00:00Z",
        "updated_at": "2024-01-02T04:00:00Z",
        "id": "10101010-1010-4010-8010-101010101010",
    },
    {
        "department_id": "cdead00b-74fd-4760-bb49-f2b36fe46964",
        "name": "South Prairie Special Education Support",
        "code": "SPED_SP",
        "created_at": "2024-01-02T04:10:00Z",
        "updated_at": "2024-01-02T04:10:00Z",
        "id": "11111111-1111-4111-8111-111111111111",
    },
    {
        "department_id": "687b59dd-7f8e-4d5b-8061-359dc8b86ecc",
        "name": "South Prairie Art",
        "code": "ART_SP",
        "created_at": "2024-01-02T04:20:00Z",
        "updated_at": "2024-01-02T04:20:00Z",
        "id": "12121212-1212-4212-8212-121212121212",
    },
    {
        "department_id": "408886ef-c8e2-4199-86be-089555f69db5",
        "name": "South Prairie Reading Intervention",
        "code": "READINT_SP",
        "created_at": "2024-01-02T04:30:00Z",
        "updated_at": "2024-01-02T04:30:00Z",
        "id": "13131313-1313-4313-8313-131313131313",
    },
    {
        "department_id": "1de20956-ec18-4804-b30f-4ad9eb7e0827",
        "name": "South Prairie Social-Emotional Learning",
        "code": "SEL_SP",
        "created_at": "2024-01-02T04:40:00Z",
        "updated_at": "2024-01-02T04:40:00Z",
        "id": "14141414-1414-4414-8414-141414141414",
    },

    # Heritage
    {
        "department_id": "d86cff59-6ded-4435-9f58-327934f47e59",
        "name": "Heritage Reading",
        "code": "READ_HE",
        "created_at": "2024-01-02T05:00:00Z",
        "updated_at": "2024-01-02T05:00:00Z",
        "id": "15151515-1515-4515-8515-151515151515",
    },
    {
        "department_id": "86c4adde-e5bd-4c43-9c78-9fff47800319",
        "name": "Heritage Special Education Support",
        "code": "SPED_HE",
        "created_at": "2024-01-02T05:10:00Z",
        "updated_at": "2024-01-02T05:10:00Z",
        "id": "16161616-1616-4616-8616-161616161616",
    },
    {
        "department_id": "97175810-7874-4bbc-b7a6-023fe04d5829",
        "name": "Heritage Music",
        "code": "MUSIC_HE",
        "created_at": "2024-01-02T05:20:00Z",
        "updated_at": "2024-01-02T05:20:00Z",
        "id": "17171717-1717-4717-8717-171717171717",
    },
    {
        "department_id": "1b1f7a10-d786-4fd5-99af-4229eb8283fb",
        "name": "Heritage Math Intervention",
        "code": "MATHINT_HE",
        "created_at": "2024-01-02T05:30:00Z",
        "updated_at": "2024-01-02T05:30:00Z",
        "id": "18181818-1818-4818-8818-181818181818",
    },
    {
        "department_id": "cac64beb-8960-458d-b247-da7c86c07356",
        "name": "Heritage Social-Emotional Learning",
        "code": "SEL_HE",
        "created_at": "2024-01-02T05:40:00Z",
        "updated_at": "2024-01-02T05:40:00Z",
        "id": "19191919-1919-4919-8919-191919191919",
    },

    # North Ridge
    {
        "department_id": "97d4c03c-2f34-4079-a8a9-ad33ea1b3be7",
        "name": "North Ridge Reading",
        "code": "READ_NR",
        "created_at": "2024-01-02T06:00:00Z",
        "updated_at": "2024-01-02T06:00:00Z",
        "id": "1a1a1a1a-1a1a-4a1a-8a1a-1a1a1a1a1a1a",
    },
    {
        "department_id": "c3ecfa17-7719-4778-ac6f-0ec370460cf8",
        "name": "North Ridge Special Education Support",
        "code": "SPED_NR",
        "created_at": "2024-01-02T06:10:00Z",
        "updated_at": "2024-01-02T06:10:00Z",
        "id": "1b1b1b1b-1b1b-4b1b-8b1b-1b1b1b1b1b1b",
    },
    {
        "department_id": "9ed3b88b-fa03-4f5a-b3be-fcf789fdb977",
        "name": "North Ridge Music",
        "code": "MUSIC_NR",
        "created_at": "2024-01-02T06:20:00Z",
        "updated_at": "2024-01-02T06:20:00Z",
        "id": "1c1c1c1c-1c1c-4c1c-8c1c-1c1c1c1c1c1c",
    },
    {
        "department_id": "4718e7cc-ad33-400c-9e4b-f1c0fdfe220d",
        "name": "North Ridge Reading Intervention",
        "code": "READINT_NR",
        "created_at": "2024-01-02T06:30:00Z",
        "updated_at": "2024-01-02T06:30:00Z",
        "id": "1d1d1d1d-1d1d-4d1d-8d1d-1d1d1d1d1d1d",
    },
    {
        "department_id": "d17dc1fb-61ab-4f68-8ee0-149f71580bb2",
        "name": "North Ridge Social-Emotional Learning",
        "code": "SEL_NR",
        "created_at": "2024-01-02T06:40:00Z",
        "updated_at": "2024-01-02T06:40:00Z",
        "id": "1e1e1e1e-1e1e-4e1e-8e1e-1e1e1e1e1e1e",
    },
]


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion from Python/CSV-ish value to appropriate DB-bound value."""
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

    # Otherwise, pass raw through and let DB cast (UUID, timestamps, etc.)
    return raw


def upgrade() -> None:
    """Load seed data for subjects from inline SEED_ROWS.

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
        log.info("No seed rows defined for %s", TABLE_NAME)
        return

    inserted = 0
    for raw_row in rows:
        row: dict = {}

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

    log.info("Inserted %s rows into %s from inline SEED_ROWS", inserted, TABLE_NAME)


def downgrade() -> None:
    """Best-effort removal of the seeded subject rows based on SEED_ROWS ids."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(TABLE_NAME):
        log.warning("Table %s does not exist; skipping delete", TABLE_NAME)
        return

    metadata = sa.MetaData()
    table = sa.Table(TABLE_NAME, metadata, autoload_with=bind)

    ids = [row["id"] for row in SEED_ROWS if row.get("id")]
    if not ids:
        log.info("No ids found in SEED_ROWS for %s; skipping delete", TABLE_NAME)
        return

    bind.execute(table.delete().where(table.c.id.in_(ids)))
    log.info("Deleted %s seeded rows from %s based on SEED_ROWS", len(ids), TABLE_NAME)
