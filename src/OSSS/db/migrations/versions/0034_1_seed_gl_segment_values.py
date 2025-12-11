from __future__ import annotations

import logging
import os

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0034_1"
down_revision = "0034"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

SKIP_GL_SEGMENTS = os.getenv("SKIP_GL_SEGMENTS", "").lower() in ("1", "true", "yes", "on")

TABLE_NAME = "gl_segment_values"

# Inline seed data for gl_segment_values
# Columns: id, code, name, active, segment_id
SEED_ROWS = [
    {
        "id": "79ddd98c-dc01-44d4-be3a-e6498f7fc53c",
        "code": "10",
        "name": "General Fund",
        "active": True,
        "segment_id": "2b8a4b38-8e3e-41b2-b58e-9c0f1b4e0a01",
    },
    {
        "id": "5e8399e7-3f97-4adf-8293-8e9621decd0a",
        "code": "1000",
        "name": "Instruction",
        "active": True,
        "segment_id": "3cf0de8b-5e3a-4f7c-9c65-0c08d8e2b702",
    },
    {
        "id": "33eb8e3b-91ba-4d89-b6ad-de7c0c60e2b2",
        "code": "000",
        "name": "Regular Education",
        "active": True,
        "segment_id": "9c8b0f24-4d92-4b7f-9b66-32b9d8f3a903",
    },
    {
        "id": "34caeed1-a179-4071-8050-f9ff0daf5f1a",
        "code": "100",
        "name": "Salaries",
        "active": True,
        "segment_id": "7b2c1534-47d4-4b42-9a39-6a2f9a3f5e04",
    },
    {
        "id": "7276147a-8ed5-4c2f-a900-e449fc27ef50",
        "code": "0000",
        "name": "No Project",
        "active": True,
        "segment_id": "f10b3d5f-0dd8-4b74-9a6b-bf17a8eddd05",
    },
    {
        "id": "d7891e56-bd80-4da6-a5f4-f014b6017197",
        "code": "000",
        "name": "General",
        "active": True,
        "segment_id": "6a2f7b8c-3245-4a1f-8e29-0b3c4d5e6f06",
    },
    {
        "id": "7f3b1cfd-aa51-4ce6-a1a8-b9e603c7497f",
        "code": "10",
        "name": "General Fund",
        "active": True,
        "segment_id": "2b8a4b38-8e3e-41b2-b58e-9c0f1b4e0a01",
    },
    {
        "id": "747cf5ae-9e0c-4adc-a09b-4a522eeb4546",
        "code": "1000",
        "name": "Instruction",
        "active": True,
        "segment_id": "3cf0de8b-5e3a-4f7c-9c65-0c08d8e2b702",
    },
    {
        "id": "ab82069d-1688-4acd-9b24-5354ec06962b",
        "code": "000",
        "name": "Regular Education",
        "active": True,
        "segment_id": "9c8b0f24-4d92-4b7f-9b66-32b9d8f3a903",
    },
    {
        "id": "5e963b7c-f9b4-4280-8e99-046a033ae2bb",
        "code": "100",
        "name": "Salaries",
        "active": True,
        "segment_id": "7b2c1534-47d4-4b42-9a39-6a2f9a3f5e04",
    },
    {
        "id": "0777c43e-016b-47d6-bee3-d0edc89322e7",
        "code": "0000",
        "name": "Instructional Support Levy (ISL)",
        "active": True,
        "segment_id": "f10b3d5f-0dd8-4b74-9a6b-bf17a8eddd05",
    },
    {
        "id": "4704a543-6909-4387-b306-b3b461a16ef9",
        "code": "810",
        "name": "Object 810",
        "active": True,
        "segment_id": "6a2f7b8c-3245-4a1f-8e29-0b3c4d5e6f06",
    },
]


def _coerce_value(col: sa.Column, raw):
    """
    Best-effort coercion from Python/inline value to appropriate DB-bound value.

    For string columns, keep empty strings as "" instead of converting
    them to NULL, so we don't violate NOT NULL constraints on name/code fields.
    """
    t = col.type

    # Handle None separately
    if raw is None:
        return None

    # Empty string handling depends on column type
    if raw == "":
        if isinstance(t, (sa.String, sa.Text)):
            return ""
        return None

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

    # Otherwise, pass raw through and let DB/SQLAlchemy cast
    return raw


def upgrade() -> None:
    """Load seed data for gl_segment_values from inline SEED_ROWS."""
    if SKIP_GL_SEGMENTS:
        log.warning("SKIP_GL_SEGMENTS flag is ON — skipping seeding for gl_segments")
        return

    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # Ensure target table exists
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
        values: dict[str, object] = {}

        # Map & coerce by actual table columns
        for col in table.columns:
            if col.name not in raw_row:
                continue
            raw_val = raw_row[col.name]
            value = _coerce_value(col, raw_val)
            values[col.name] = value

        if not values:
            continue

        nested = bind.begin_nested()
        try:
            bind.execute(table.insert().values(**values))
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
    """No-op downgrade; seed data is left in place."""
    if SKIP_GL_SEGMENTS:
        log.warning("SKIP_GL_SEGMENTS flag is ON — skipping seeding for gl_segments")
        return

    pass
