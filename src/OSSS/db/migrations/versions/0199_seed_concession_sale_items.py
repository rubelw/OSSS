from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0199"
down_revision = "0198"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "concession_sale_items"

# Inline seed rows for concession_sale_items
# Assumes concession_items include:
# - cda1201e-... : Buttered Popcorn @ 300 cents
# - 2d2fd20a-... : Bottled Water @ 200 cents
# - 7ff7a30e-... : Candy Variety Pack @ 250 cents
# - 60933907-... : Hot Dog @ 350 cents
# - 3103982f-... : Nachos with Cheese @ 400 cents
#
# And concession_sales IDs from the previous migration (0198).
SEED_ROWS = [
    # Jordan Miller buys 2 popcorns and 1 bottled water
    {
        "sale_id": "1e46fcec-e57a-58da-bffd-e5d19b233dc8",
        "item_id": "cda1201e-f031-5175-b6b2-9d036be6d674",  # Buttered Popcorn
        "quantity": 2,
        "line_total_cents": 600,  # 2 * 300
        "id": "e361327f-912a-599f-91f3-41f45c1d8d30",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
    },
    {
        "sale_id": "1e46fcec-e57a-58da-bffd-e5d19b233dc8",
        "item_id": "2d2fd20a-fba6-50e3-812a-f3d5ae2a8fc9",  # Bottled Water
        "quantity": 1,
        "line_total_cents": 200,  # 1 * 200
        "id": "bdf31601-5528-569c-aa96-bd096833729c",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
    },
    # Taylor Nguyen buys 3 hot dogs
    {
        "sale_id": "06cd1e96-88f8-54d6-aa3a-cc2de0874326",
        "item_id": "60933907-914d-5869-a36c-61315747bfdb",  # Hot Dog
        "quantity": 3,
        "line_total_cents": 1050,  # 3 * 350
        "id": "8f392404-4ccf-5c3a-b594-2d9caf6b0c78",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
    },
    # Riley Johnson buys 1 order of nachos
    {
        "sale_id": "7068ba36-3e34-5679-af63-cf612c10b644",
        "item_id": "3103982f-31e0-536b-8bb5-25d43ce8b3ed",  # Nachos with Cheese
        "quantity": 1,
        "line_total_cents": 400,  # 1 * 400
        "id": "689bfe4c-3229-5cda-9ebc-3dc75e576423",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
    },
    # Alex Martinez buys 2 candy variety packs
    {
        "sale_id": "77872e94-4291-508b-b25e-391f58e369c8",
        "item_id": "7ff7a30e-3e08-55d8-a8af-ea92621cafc8",  # Candy Variety Pack
        "quantity": 2,
        "line_total_cents": 500,  # 2 * 250
        "id": "0b722923-240e-5539-ac5c-1a0036c5d76c",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
    },
]


def upgrade() -> None:
    """Load seed data for concession_sale_items from inline SEED_ROWS.

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
        row = {col.name: raw_row[col.name] for col in table.columns if col.name in raw_row}

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
    # No-op downgrade; seed data is left in place.
    pass
