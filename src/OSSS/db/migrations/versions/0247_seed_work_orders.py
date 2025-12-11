from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0247"
down_revision = "0246_1"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "work_orders"

# Inline seed rows, aligned with maintenance_requests in 0246
SEED_ROWS = [
    {
        # Linked to maintenance request: leaking faucet in staff restroom
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "building_id": "2fcc53b4-7367-5852-9afb-ffdecafad618",
        "space_id": "8b3aa9d0-8d1e-5d94-8c02-9eb3a38e7e88",
        "asset_id": "6c7a568b-721c-523d-b5c2-ce3fd6029630",
        "request_id": "8c4709e2-bd28-5d3f-b0c2-f682bf251df5",
        "status": "OPEN",
        "priority": "MEDIUM",
        "category": "PLUMBING",
        "summary": "Repair leaking faucet in staff restroom",
        "description": "Diagnose and repair persistent drip from staff restroom faucet near Room 210. Verify no damage to cabinet below.",
        "requested_due_at": "2024-01-05T00:00:00Z",
        "scheduled_start_at": "2024-01-02T13:00:00Z",
        "scheduled_end_at": "2024-01-02T15:00:00Z",
        "completed_at": None,
        "assigned_to_user_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "materials_cost": 25,
        "labor_cost": 75,
        "other_cost": 0,
        "attributes": {},
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
        "id": "3e3aec0f-13ac-5571-93ba-55376121619f",
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
    """Insert inline seed data for work_orders."""
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
