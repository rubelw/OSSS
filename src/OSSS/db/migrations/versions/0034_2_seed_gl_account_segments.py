from __future__ import annotations

import logging
import os

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0034_2"
down_revision = "0034_1"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

SKIP_GL_SEGMENTS = os.getenv("SKIP_GL_SEGMENTS", "").lower() in ("1", "true", "yes", "on")

TABLE_NAME = "gl_account_segments"

# Inline seed data for gl_account_segments
# Columns (matching GLAccountSegment model):
#   id, account_id, segment_id, value_id
SEED_ROWS = [
    # Account: 6a75aa46-... ("General Fund / Instruction / Regular Education / Salaries / No Project / General")
    {
        "id": "02a16832-a68c-42bc-9dbf-dfa66aea4273",
        "account_id": "6a75aa46-a757-56fd-a8e3-53ada0559dad",
        "segment_id": "2b8a4b38-8e3e-41b2-b58e-9c0f1b4e0a01",  # FUND
        "value_id": "79ddd98c-dc01-44d4-be3a-e6498f7fc53c",   # code 10, "General Fund"
    },
    {
        "id": "5ddfbf1d-5719-4339-8c43-6942d03648fd",
        "account_id": "6a75aa46-a757-56fd-a8e3-53ada0559dad",
        "segment_id": "3cf0de8b-5e3a-4f7c-9c65-0c08d8e2b702",  # FACILITY
        "value_id": "5e8399e7-3f97-4adf-8293-8e9621decd0a",   # code 1000, "Instruction"
    },
    {
        "id": "34cf48e0-90d3-4b40-8c22-e4e92b4de6e4",
        "account_id": "6a75aa46-a757-56fd-a8e3-53ada0559dad",
        "segment_id": "9c8b0f24-4d92-4b7f-9b66-32b9d8f3a903",  # FUNCTION
        "value_id": "33eb8e3b-91ba-4d89-b6ad-de7c0c60e2b2",   # code 000, "Regular Education"
    },
    {
        "id": "c1a95b54-b720-4067-a2dc-d3be3a9a2975",
        "account_id": "6a75aa46-a757-56fd-a8e3-53ada0559dad",
        "segment_id": "7b2c1534-47d4-4b42-9a39-6a2f9a3f5e04",  # PROGRAM
        "value_id": "34caeed1-a179-4071-8050-f9ff0daf5f1a",   # code 100, "Salaries"
    },
    {
        "id": "a8966dc6-0695-4e53-9655-3bbc2c537506",
        "account_id": "6a75aa46-a757-56fd-a8e3-53ada0559dad",
        "segment_id": "f10b3d5f-0dd8-4b74-9a6b-bf17a8eddd05",  # PROJECT
        "value_id": "7276147a-8ed5-4c2f-a900-e449fc27ef50",   # code 0000, "No Project"
    },
    {
        "id": "f99587ee-14f3-473c-b5d7-fdd60b19a870",
        "account_id": "6a75aa46-a757-56fd-a8e3-53ada0559dad",
        "segment_id": "6a2f7b8c-3245-4a1f-8e29-0b3c4d5e6f06",  # OBJECT
        "value_id": "d7891e56-bd80-4da6-a5f4-f014b6017197",   # code 000, "General"
    },

    # Account: b2b1b34f-... ("General Fund / Instruction / Regular Education / Salaries / ISL / Object 810")
    {
        "id": "4de02f94-6f9e-4f9a-940c-63f2c4e4a9a3",
        "account_id": "b2b1b34f-2552-50d3-ad59-0db26521a897",
        "segment_id": "2b8a4b38-8e3e-41b2-b58e-9c0f1b4e0a01",  # FUND
        "value_id": "7f3b1cfd-aa51-4ce6-a1a8-b9e603c7497f",   # code 10, "General Fund"
    },
    {
        "id": "d3e1760c-fb82-4bf9-8766-fb4919825e30",
        "account_id": "b2b1b34f-2552-50d3-ad59-0db26521a897",
        "segment_id": "3cf0de8b-5e3a-4f7c-9c65-0c08d8e2b702",  # FACILITY
        "value_id": "747cf5ae-9e0c-4adc-a09b-4a522eeb4546",   # code 1000, "Instruction"
    },
    {
        "id": "5e32f85f-b63b-4d69-acdf-1306eaaef5df",
        "account_id": "b2b1b34f-2552-50d3-ad59-0db26521a897",
        "segment_id": "9c8b0f24-4d92-4b7f-9b66-32b9d8f3a903",  # FUNCTION
        "value_id": "ab82069d-1688-4acd-9b24-5354ec06962b",   # code 000, "Regular Education"
    },
    {
        "id": "6ec48760-9901-46f8-b138-772e95de102e",
        "account_id": "b2b1b34f-2552-50d3-ad59-0db26521a897",
        "segment_id": "7b2c1534-47d4-4b42-9a39-6a2f9a3f5e04",  # PROGRAM
        "value_id": "5e963b7c-f9b4-4280-8e99-046a033ae2bb",   # code 100, "Salaries"
    },
    {
        "id": "b8de275d-1e46-4fb3-88e0-9ceefd6db007",
        "account_id": "b2b1b34f-2552-50d3-ad59-0db26521a897",
        "segment_id": "f10b3d5f-0dd8-4b74-9a6b-bf17a8eddd05",  # PROJECT
        "value_id": "0777c43e-016b-47d6-bee3-d0edc89322e7",   # code 0000, "Instructional Support Levy (ISL)"
    },
    {
        "id": "e98492cf-7225-4315-b550-9ff534e90451",
        "account_id": "b2b1b34f-2552-50d3-ad59-0db26521a897",
        "segment_id": "6a2f7b8c-3245-4a1f-8e29-0b3c4d5e6f06",  # OBJECT
        "value_id": "4704a543-6909-4387-b306-b3b461a16ef9",   # code 810, "Object 810"
    },
]


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion from Python/CSV-style value to appropriate DB value."""
    if raw == "" or raw is None:
        return None

    t = col.type

    # Boolean needs special handling because SQLAlchemy is strict
    if isinstance(t, sa.Boolean):
        if isinstance(raw, str):
            v = raw.strip().lower()
            if v in ("true", "t", "1", "yes", "y", "on"):
                return True
            if v in ("false", "f", "0", "no", "n", "off"):
                return False
            log.warning(
                "Invalid boolean for %s.%s: %r; using NULL",
                TABLE_NAME,
                col.name,
                raw,
            )
            return None
        return bool(raw)

    # Let DB cast strings/UUIDs/ints/etc.
    return raw


def upgrade() -> None:
    """Seed gl_account_segments from inline SEED_ROWS, with per-row SAVEPOINTs."""
    if SKIP_GL_SEGMENTS:
        log.warning(
            "SKIP_GL_SEGMENTS flag is ON — skipping seeding for %s",
            TABLE_NAME,
        )
        return

    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(TABLE_NAME):
        log.warning("Table %s does not exist; skipping seed", TABLE_NAME)
        return

    if not SEED_ROWS:
        log.info("No inline seed rows defined for %s; nothing to insert", TABLE_NAME)
        return

    metadata = sa.MetaData()
    table = sa.Table(TABLE_NAME, metadata, autoload_with=bind)

    inserted = 0
    for raw_row in SEED_ROWS:
        row: dict[str, object] = {}

        # Only pass columns that actually exist on gl_account_segments
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

    log.info("Inserted %s inline seed rows into %s", inserted, TABLE_NAME)


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    if SKIP_GL_SEGMENTS:
        log.warning(
            "SKIP_GL_SEGMENTS flag is ON — skipping downgrade operations for %s",
            TABLE_NAME,
        )
        return

    pass
