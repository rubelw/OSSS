from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0249"
down_revision = "0248"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "work_order_tasks"

# Inline seed rows with realistic maintenance tasks for the leaking faucet work order
SEED_ROWS = [
    {
        "work_order_id": "3e3aec0f-13ac-5571-93ba-55376121619f",
        "seq": 1,
        "title": "Shut off water supply and verify isolation",
        "is_mandatory": True,
        "status": "completed",
        "completed_at": "2024-01-01T01:15:00Z",
        "notes": "Main restroom shutoff closed and faucet verified depressurized.",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:15:00Z",
        "id": "b0bc1e6c-141d-5195-b578-1988f7ceec9b",
    },
    {
        "work_order_id": "3e3aec0f-13ac-5571-93ba-55376121619f",
        "seq": 2,
        "title": "Remove faucet handle and failed cartridge",
        "is_mandatory": True,
        "status": "completed",
        "completed_at": "2024-01-01T02:10:00Z",
        "notes": "Handle and trim removed; worn cartridge and O-rings taken out.",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:10:00Z",
        "id": "8460ab83-9dc5-52cd-bd09-c61e89d615a9",
    },
    {
        "work_order_id": "3e3aec0f-13ac-5571-93ba-55376121619f",
        "seq": 3,
        "title": "Install new cartridge and reassemble faucet",
        "is_mandatory": True,
        "status": "completed",
        "completed_at": "2024-01-01T03:05:00Z",
        "notes": "New cartridge installed with fresh O-rings; faucet reassembled.",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:05:00Z",
        "id": "304478fd-6fc4-5ea8-bb30-bd8ddf87ae3e",
    },
    {
        "work_order_id": "3e3aec0f-13ac-5571-93ba-55376121619f",
        "seq": 4,
        "title": "Restore water and check for leaks",
        "is_mandatory": True,
        "status": "completed",
        "completed_at": "2024-01-01T04:10:00Z",
        "notes": "Water turned back on; no leaks observed at faucet or supply lines.",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:10:00Z",
        "id": "b0f1111e-cfd7-5fb9-aa66-1fe3cdd3430a",
    },
    {
        "work_order_id": "3e3aec0f-13ac-5571-93ba-55376121619f",
        "seq": 5,
        "title": "Clean work area and update work order notes",
        "is_mandatory": False,
        "status": "completed",
        "completed_at": "2024-01-01T05:05:00Z",
        "notes": "Sink area wiped down; tools and old parts removed; work order updated.",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:05:00Z",
        "id": "6b549e1a-94c4-5f90-8a50-fbee7779c559",
    },
]


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion from seed value to appropriate Python/DB value."""
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

    # Otherwise, pass raw through and let DB cast
    return raw


def upgrade() -> None:
    """Insert inline seed data for work_order_tasks."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(TABLE_NAME):
        log.warning("Table %s does not exist; skipping seed", TABLE_NAME)
        return

    metadata = sa.MetaData()
    table = sa.Table(TABLE_NAME, metadata, autoload_with=bind)

    if not SEED_ROWS:
        log.info("No inline seed rows defined for %s; skipping", TABLE_NAME)
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

    log.info("Inserted %s inline rows into %s", inserted, TABLE_NAME)


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
