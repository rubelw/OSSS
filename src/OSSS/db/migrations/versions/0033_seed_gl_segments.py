from __future__ import annotations

import logging
import os

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0033"
down_revision = "0032_1"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

SKIP_GL_SEGMENTS = os.getenv("SKIP_GL_SEGMENTS", "").lower() in ("1", "true", "yes", "y", "on")

TABLE_NAME = "gl_segments"

# Inline seed data for gl_segments
# Columns: id, code, name, seq, length, required
SEED_ROWS = [
    {
        "id": "2b8a4b38-8e3e-41b2-b58e-9c0f1b4e0a01",
        "code": "FUND",
        "name": "Fund",
        "seq": 1,
        "length": 2,
        "required": True,
    },
    {
        "id": "3cf0de8b-5e3a-4f7c-9c65-0c08d8e2b702",
        "code": "FACILITY",
        "name": "Facility",
        "seq": 2,
        "length": 4,
        "required": True,
    },
    {
        "id": "9c8b0f24-4d92-4b7f-9b66-32b9d8f3a903",
        "code": "FUNCTION",
        "name": "Function",
        "seq": 3,
        "length": 4,
        "required": True,
    },
    {
        "id": "7b2c1534-47d4-4b42-9a39-6a2f9a3f5e04",
        "code": "PROGRAM",
        "name": "Program",
        "seq": 4,
        "length": 3,
        "required": True,
    },
    {
        "id": "f10b3d5f-0dd8-4b74-9a6b-bf17a8eddd05",
        "code": "PROJECT",
        "name": "Project",
        "seq": 5,
        "length": 4,
        "required": True,
    },
    {
        "id": "6a2f7b8c-3245-4a1f-8e29-0b3c4d5e6f06",
        "code": "OBJECT",
        "name": "Object",
        "seq": 6,
        "length": 3,
        "required": False,
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

    # Let DB cast integers / strings / etc.
    return raw


def upgrade() -> None:
    """Seed gl_segments from inline SEED_ROWS with per-row SAVEPOINTs."""
    if SKIP_GL_SEGMENTS:
        log.warning("SKIP_GL_SEGMENTS flag is ON — skipping seeding for %s", TABLE_NAME)
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

        # Only pass known columns on gl_segments
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
    """No-op downgrade; seed data for gl_segments is left in place."""
    if SKIP_GL_SEGMENTS:
        log.warning(
            "SKIP_GL_SEGMENTS flag is ON — skipping downgrade operations for %s",
            TABLE_NAME,
        )
        return

    # Intentionally do nothing to preserve seeded reference data.
    pass
