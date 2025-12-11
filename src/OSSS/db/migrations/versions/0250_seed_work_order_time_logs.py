from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0250"
down_revision = "0249"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "work_order_time_logs"

# Inline seed rows with realistic maintenance time logs
# for the leaking faucet work order.
SEED_ROWS = [
    {
        # Diagnose leak and isolate water
        "work_order_id": "3e3aec0f-13ac-5571-93ba-55376121619f",
        "user_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "started_at": "2024-01-01T08:30:00Z",
        "ended_at": "2024-01-01T09:00:00Z",
        "hours": 0.5,
        "hourly_rate": 35.0,
        "cost": 17.50,
        "notes": "Diagnosed faucet leak and located shutoff for restroom sink.",
        "created_at": "2024-01-01T08:30:00Z",
        "updated_at": "2024-01-01T09:00:00Z",
        "id": "bb3c4939-915f-5ec1-8504-aa90b5d0c337",
    },
    {
        # Disassemble faucet and remove failed cartridge
        "work_order_id": "3e3aec0f-13ac-5571-93ba-55376121619f",
        "user_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "started_at": "2024-01-01T09:00:00Z",
        "ended_at": "2024-01-01T09:30:00Z",
        "hours": 0.5,
        "hourly_rate": 35.0,
        "cost": 17.50,
        "notes": "Shut off water, removed handle and trim, and pulled worn cartridge.",
        "created_at": "2024-01-01T09:00:00Z",
        "updated_at": "2024-01-01T09:30:00Z",
        "id": "7500bf7b-ac17-5e69-ae61-4e597e550e3f",
    },
    {
        # Install new cartridge and reassemble
        "work_order_id": "3e3aec0f-13ac-5571-93ba-55376121619f",
        "user_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "started_at": "2024-01-01T09:30:00Z",
        "ended_at": "2024-01-01T10:00:00Z",
        "hours": 0.5,
        "hourly_rate": 35.0,
        "cost": 17.50,
        "notes": "Installed replacement cartridge and new O-rings; faucet reassembled.",
        "created_at": "2024-01-01T09:30:00Z",
        "updated_at": "2024-01-01T10:00:00Z",
        "id": "a9201980-9a1e-54fd-b764-92b4d5a0a434",
    },
    {
        # Test for leaks and adjust flow
        "work_order_id": "3e3aec0f-13ac-5571-93ba-55376121619f",
        "user_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "started_at": "2024-01-01T10:00:00Z",
        "ended_at": "2024-01-01T10:10:00Z",
        "hours": 0.25,
        "hourly_rate": 35.0,
        "cost": 8.75,
        "notes": "Restored water; checked hot/cold operation and verified no dripping.",
        "created_at": "2024-01-01T10:00:00Z",
        "updated_at": "2024-01-01T10:10:00Z",
        "id": "05f37d74-083f-5c80-88e9-09f0eb6f931f",
    },
    {
        # Cleanup and documentation
        "work_order_id": "3e3aec0f-13ac-5571-93ba-55376121619f",
        "user_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "started_at": "2024-01-01T10:10:00Z",
        "ended_at": "2024-01-01T10:20:00Z",
        "hours": 0.25,
        "hourly_rate": 35.0,
        "cost": 8.75,
        "notes": "Cleaned area, removed old parts, and updated work order notes.",
        "created_at": "2024-01-01T10:10:00Z",
        "updated_at": "2024-01-01T10:20:00Z",
        "id": "cbf869d9-22a1-536e-8097-b1c0abfada8b",
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

    # Otherwise, pass raw through and let DB/driver cast
    return raw


def upgrade() -> None:
    """Insert inline seed data for work_order_time_logs."""
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

        # Explicit nested transaction (SAVEPOINT)
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
