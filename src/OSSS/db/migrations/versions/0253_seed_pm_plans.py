from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0253"
down_revision = "0252"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "pm_plans"

# Inline, realistic PM plan seed data
SEED_ROWS = [
    {
        # RTU on main academic building
        "asset_id": "6c7a568b-721c-523d-b5c2-ce3fd6029630",
        "building_id": "2fcc53b4-7367-5852-9afb-ffdecafad618",
        "name": "Quarterly Filter Change – RTU-1",
        "frequency": "quarterly",
        "next_due_at": "2024-01-01T01:00:00Z",
        "last_completed_at": "2023-10-01T01:00:00Z",
        "active": True,
        "procedure": (
            "1. Lock out/tag out unit.\n"
            "2. Remove access panels.\n"
            "3. Replace return and outside air filters.\n"
            "4. Inspect belts and electrical connections.\n"
            "5. Restore power and verify operation."
        ),
        "attributes": {
            "trade": "HVAC",
            "estimated_hours": 1.0,
            "seasonal_priority": "high",
        },
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
        "id": "c0f3ca9f-e837-5dae-b69c-c30a2beb1c62",
    },
    {
        # Boiler annual service
        "asset_id": "6c7a568b-721c-523d-b5c2-ce3fd6029630",
        "building_id": "2fcc53b4-7367-5852-9afb-ffdecafad618",
        "name": "Annual Boiler Inspection and Service",
        "frequency": "annual",
        "next_due_at": "2024-01-01T02:00:00Z",
        "last_completed_at": "2023-01-01T02:00:00Z",
        "active": True,
        "procedure": (
            "Perform full combustion analysis, clean burners and heat exchanger, "
            "verify safeties, and update inspection tag per state requirements."
        ),
        "attributes": {
            "trade": "mechanical",
            "requires_vendor": True,
            "vendor": "Midwest Boiler Services",
        },
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
        "id": "9800631b-7b0e-5f80-a90d-bb9173ee73fc",
    },
    {
        # Roof walk-through
        "asset_id": "6c7a568b-721c-523d-b5c2-ce3fd6029630",
        "building_id": "2fcc53b4-7367-5852-9afb-ffdecafad618",
        "name": "Semiannual Roof Inspection",
        "frequency": "semiannual",
        "next_due_at": "2024-01-01T03:00:00Z",
        "last_completed_at": "2023-07-01T03:00:00Z",
        "active": False,
        "procedure": (
            "Inspect roof membrane, flashing, drains, and penetrations for damage or debris. "
            "Document any leaks or ponding and create work orders as needed."
        ),
        "attributes": {
            "trade": "general maintenance",
            "safety_requirements": ["fall_protection"],
        },
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
        "id": "6c48592b-3055-5bfe-8108-5af9f33e6d44",
    },
    {
        # Extinguisher check
        "asset_id": "6c7a568b-721c-523d-b5c2-ce3fd6029630",
        "building_id": "2fcc53b4-7367-5852-9afb-ffdecafad618",
        "name": "Monthly Fire Extinguisher Inspection – East Wing",
        "frequency": "monthly",
        "next_due_at": "2024-01-01T04:00:00Z",
        "last_completed_at": "2023-12-01T04:00:00Z",
        "active": True,
        "procedure": (
            "Verify extinguishers are in place, accessible, fully charged, tagged, "
            "and free of visible damage; initial inspection tag."
        ),
        "attributes": {
            "trade": "life safety",
            "route_label": "East Wing corridor",
        },
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
        "id": "4f0b4229-bf47-59d5-b725-b376a42a00e1",
    },
    {
        # Long-cycle sprinkler test
        "asset_id": "6c7a568b-721c-523d-b5c2-ce3fd6029630",
        "building_id": "2fcc53b4-7367-5852-9afb-ffdecafad618",
        "name": "Five-Year Full Fire Sprinkler Test",
        "frequency": "every 5 years",
        "next_due_at": "2024-01-01T05:00:00Z",
        "last_completed_at": "2019-01-01T05:00:00Z",
        "active": False,
        "procedure": (
            "Coordinate with fire protection vendor to perform five-year internal "
            "pipe inspection, main drain test, and full system functional test."
        ),
        "attributes": {
            "trade": "life safety",
            "requires_vendor": True,
            "standard": "NFPA 25",
        },
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
        "id": "8ce2a85e-7863-544b-b32d-db21a420a3b1",
    },
]


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion from inline seed value to appropriate Python/DB value."""
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

    # JSON, numeric, and timestamp strings are passed through and cast by DB
    return raw


def upgrade() -> None:
    """Insert inline seed data for pm_plans."""
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
