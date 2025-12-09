from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa

from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0051"
down_revision = "0050"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "grade_levels"


def upgrade() -> None:
    """Seed grade_levels with inline data (no CSV)."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(TABLE_NAME):
        log.warning("Table %s does not exist; skipping seed", TABLE_NAME)
        return

    metadata = sa.MetaData()
    table = sa.Table(TABLE_NAME, metadata, autoload_with=bind)

    seed_rows = [
        # DCG High School (9–12)
        {
            "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
            "name": "NINETH",
            "ordinal": 1,
            "created_at": "2024-01-01T01:00:00Z",
            "updated_at": "2024-01-01T01:00:00Z",
            "id": "21212121-2121-4121-8121-212121212121",
        },
        {
            "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
            "name": "TENTH",
            "ordinal": 2,
            "created_at": "2024-01-01T01:05:00Z",
            "updated_at": "2024-01-01T01:05:00Z",
            "id": "22222222-2222-4222-8222-222222222222",
        },
        {
            "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
            "name": "ELEVENTH",
            "ordinal": 3,
            "created_at": "2024-01-01T01:10:00Z",
            "updated_at": "2024-01-01T01:10:00Z",
            "id": "23232323-2323-4323-8323-232323232323",
        },
        {
            "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
            "name": "TWELFTH",
            "ordinal": 4,
            "created_at": "2024-01-01T01:15:00Z",
            "updated_at": "2024-01-01T01:15:00Z",
            "id": "24242424-2424-4424-8424-242424242424",
        },

        # DCG Middle School (6–8)
        {
            "school_id": "119caaef-ef97-5364-b179-388e108bd40d",
            "name": "SIXTH",
            "ordinal": 1,
            "created_at": "2024-01-01T02:00:00Z",
            "updated_at": "2024-01-01T02:00:00Z",
            "id": "25252525-2525-4525-8525-252525252525",
        },
        {
            "school_id": "119caaef-ef97-5364-b179-388e108bd40d",
            "name": "SEVENTH",
            "ordinal": 2,
            "created_at": "2024-01-01T02:05:00Z",
            "updated_at": "2024-01-01T02:05:00Z",
            "id": "26262626-2626-4626-8626-262626262626",
        },
        {
            "school_id": "119caaef-ef97-5364-b179-388e108bd40d",
            "name": "EIGHTH",
            "ordinal": 3,
            "created_at": "2024-01-01T02:10:00Z",
            "updated_at": "2024-01-01T02:10:00Z",
            "id": "27272727-2727-4727-8727-272727272727",
        },

        # South Prairie Elementary (PreK–5)
        {
            "school_id": "b122fcb4-2864-593c-9b05-2188ef296db4",
            "name": "PREK",
            "ordinal": 1,
            "created_at": "2024-01-01T03:00:00Z",
            "updated_at": "2024-01-01T03:00:00Z",
            "id": "28282828-2828-4828-8828-282828282828",
        },
        {
            "school_id": "b122fcb4-2864-593c-9b05-2188ef296db4",
            "name": "KINDERGARTEN",
            "ordinal": 2,
            "created_at": "2024-01-01T03:05:00Z",
            "updated_at": "2024-01-01T03:05:00Z",
            "id": "29292929-2929-4929-8929-292929292929",
        },
        {
            "school_id": "b122fcb4-2864-593c-9b05-2188ef296db4",
            "name": "FIRST",
            "ordinal": 3,
            "created_at": "2024-01-01T03:10:00Z",
            "updated_at": "2024-01-01T03:10:00Z",
            "id": "2a2a2a2a-2a2a-4a2a-8a2a-2a2a2a2a2a2a",
        },
        {
            "school_id": "b122fcb4-2864-593c-9b05-2188ef296db4",
            "name": "SECOND",
            "ordinal": 4,
            "created_at": "2024-01-01T03:15:00Z",
            "updated_at": "2024-01-01T03:15:00Z",
            "id": "2b2b2b2b-2b2b-4b2b-8b2b-2b2b2b2b2b2b",
        },
        {
            "school_id": "b122fcb4-2864-593c-9b05-2188ef296db4",
            "name": "THIRD",
            "ordinal": 5,
            "created_at": "2024-01-01T03:20:00Z",
            "updated_at": "2024-01-01T03:20:00Z",
            "id": "2c2c2c2c-2c2c-4c2c-8c2c-2c2c2c2c2c2c",
        },
        {
            "school_id": "b122fcb4-2864-593c-9b05-2188ef296db4",
            "name": "FOURTH",
            "ordinal": 6,
            "created_at": "2024-01-01T03:25:00Z",
            "updated_at": "2024-01-01T03:25:00Z",
            "id": "2d2d2d2d-2d2d-4d2d-8d2d-2d2d2d2d2d2d",
        },
        {
            "school_id": "b122fcb4-2864-593c-9b05-2188ef296db4",
            "name": "FIFTH",
            "ordinal": 7,
            "created_at": "2024-01-01T03:30:00Z",
            "updated_at": "2024-01-01T03:30:00Z",
            "id": "2e2e2e2e-2e2e-4e2e-8e2e-2e2e2e2e2e2e",
        },

        # Heritage Elementary (PreK–5)
        {
            "school_id": "df4b1423-d755-5c7f-a0ba-6908de77f61b",
            "name": "PREK",
            "ordinal": 1,
            "created_at": "2024-01-01T04:00:00Z",
            "updated_at": "2024-01-01T04:00:00Z",
            "id": "2f2f2f2f-2f2f-4f2f-8f2f-2f2f2f2f2f2f",
        },
        {
            "school_id": "df4b1423-d755-5c7f-a0ba-6908de77f61b",
            "name": "KINDERGARTEN",
            "ordinal": 2,
            "created_at": "2024-01-01T04:05:00Z",
            "updated_at": "2024-01-01T04:05:00Z",
            "id": "30303030-3030-4030-8030-303030303030",
        },
        {
            "school_id": "df4b1423-d755-5c7f-a0ba-6908de77f61b",
            "name": "FIRST",
            "ordinal": 3,
            "created_at": "2024-01-01T04:10:00Z",
            "updated_at": "2024-01-01T04:10:00Z",
            "id": "31313131-3131-4131-8131-313131313131",
        },
        {
            "school_id": "df4b1423-d755-5c7f-a0ba-6908de77f61b",
            "name": "SECOND",
            "ordinal": 4,
            "created_at": "2024-01-01T04:15:00Z",
            "updated_at": "2024-01-01T04:15:00Z",
            "id": "32323232-3232-4232-8232-323232323232",
        },
        {
            "school_id": "df4b1423-d755-5c7f-a0ba-6908de77f61b",
            "name": "THIRD",
            "ordinal": 5,
            "created_at": "2024-01-01T04:20:00Z",
            "updated_at": "2024-01-01T04:20:00Z",
            "id": "33333333-3333-4333-8333-333333333333",
        },
        {
            "school_id": "df4b1423-d755-5c7f-a0ba-6908de77f61b",
            "name": "FOURTH",
            "ordinal": 6,
            "created_at": "2024-01-01T04:25:00Z",
            "updated_at": "2024-01-01T04:25:00Z",
            "id": "34343434-3434-4434-8434-343434343434",
        },
        {
            "school_id": "df4b1423-d755-5c7f-a0ba-6908de77f61b",
            "name": "FIFTH",
            "ordinal": 7,
            "created_at": "2024-01-01T04:30:00Z",
            "updated_at": "2024-01-01T04:30:00Z",
            "id": "35353535-3535-4535-8535-353535353535",
        },

        # North Ridge Elementary (PreK–5)
        {
            "school_id": "634b8058-d620-5a5c-86b5-c0794d3a3b73",
            "name": "PREK",
            "ordinal": 1,
            "created_at": "2024-01-01T05:00:00Z",
            "updated_at": "2024-01-01T05:00:00Z",
            "id": "36363636-3636-4636-8636-363636363636",
        },
        {
            "school_id": "634b8058-d620-5a5c-86b5-c0794d3a3b73",
            "name": "KINDERGARTEN",
            "ordinal": 2,
            "created_at": "2024-01-01T05:05:00Z",
            "updated_at": "2024-01-01T05:05:00Z",
            "id": "37373737-3737-4737-8737-373737373737",
        },
        {
            "school_id": "634b8058-d620-5a5c-86b5-c0794d3a3b73",
            "name": "FIRST",
            "ordinal": 3,
            "created_at": "2024-01-01T05:10:00Z",
            "updated_at": "2024-01-01T05:10:00Z",
            "id": "38383838-3838-4838-8838-383838383838",
        },
        {
            "school_id": "634b8058-d620-5a5c-86b5-c0794d3a3b73",
            "name": "SECOND",
            "ordinal": 4,
            "created_at": "2024-01-01T05:15:00Z",
            "updated_at": "2024-01-01T05:15:00Z",
            "id": "39393939-3939-4939-8939-393939393939",
        },
        {
            "school_id": "634b8058-d620-5a5c-86b5-c0794d3a3b73",
            "name": "THIRD",
            "ordinal": 5,
            "created_at": "2024-01-01T05:20:00Z",
            "updated_at": "2024-01-01T05:20:00Z",
            "id": "3a3a3a3a-3a3a-4a3a-8a3a-3a3a3a3a3a3a",
        },
        {
            "school_id": "634b8058-d620-5a5c-86b5-c0794d3a3b73",
            "name": "FOURTH",
            "ordinal": 6,
            "created_at": "2024-01-01T05:25:00Z",
            "updated_at": "2024-01-01T05:25:00Z",
            "id": "3b3b3b3b-3b3b-4b3b-8b3b-3b3b3b3b3b3b",
        },
        {
            "school_id": "634b8058-d620-5a5c-86b5-c0794d3a3b73",
            "name": "FIFTH",
            "ordinal": 7,
            "created_at": "2024-01-01T05:30:00Z",
            "updated_at": "2024-01-01T05:30:00Z",
            "id": "3c3c3c3c-3c3c-4c3c-8c3c-3c3c3c3c3c3c",
        },
    ]

    inserted = 0
    for raw_row in seed_rows:
        nested = bind.begin_nested()
        try:
            bind.execute(table.insert().values(**raw_row))
            nested.commit()
            inserted += 1
        except (IntegrityError, DataError, StatementError) as exc:
            nested.rollback()
            log.warning(
                "Skipping inline row for %s due to error: %s. Row: %s",
                TABLE_NAME,
                exc,
                raw_row,
            )

    log.info("Inserted %s inline grade_levels rows into %s", inserted, TABLE_NAME)


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
