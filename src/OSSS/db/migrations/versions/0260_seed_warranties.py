from __future__ import annotations

import logging
from datetime import date, datetime, timezone

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0260"
down_revision = "0259"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "warranties"

ASSET_ID = "6c7a568b-721c-523d-b5c2-ce3fd6029630"
VENDOR_ID = "d7b782fe-058c-4344-b6db-15c5b7348607"

# Inline seed rows with realistic warranty data
SEED_ROWS = [
    {
        "id": "900945c6-4e67-563e-930b-6819cf1acf64",
        "asset_id": ASSET_ID,
        "vendor_id": VENDOR_ID,
        "policy_no": "WARR-HVAC-BASE-001",
        "start_date": date(2023, 7, 1),
        "end_date": date(2026, 6, 30),  # 3-year standard warranty
        "terms": "Standard manufacturer warranty covering parts only for 3 years from startup.",
        "attributes": {
            "coverage_type": "parts",
            "labor_included": False,
            "response_time": "standard",
            "notes": "Registration completed at commissioning.",
        },
        "created_at": datetime(2023, 7, 1, 8, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2023, 7, 1, 8, 0, tzinfo=timezone.utc),
    },
    {
        "id": "380353e0-226e-5303-92f8-0b1226fd0267",
        "asset_id": ASSET_ID,
        "vendor_id": VENDOR_ID,
        "policy_no": "WARR-HVAC-LABOR-002",
        "start_date": date(2023, 7, 1),
        "end_date": date(2025, 6, 30),  # 2-year labor coverage
        "terms": "Extended warranty covering labor for approved repairs during the first 2 years.",
        "attributes": {
            "coverage_type": "labor",
            "labor_included": True,
            "response_time": "next_business_day",
            "notes": "Covers normal business hours only.",
        },
        "created_at": datetime(2023, 7, 2, 9, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2023, 7, 2, 9, 0, tzinfo=timezone.utc),
    },
    {
        "id": "f2ab7b52-3b59-5538-9037-796131871202",
        "asset_id": ASSET_ID,
        "vendor_id": VENDOR_ID,
        "policy_no": "WARR-HVAC-COMP-003",
        "start_date": date(2023, 7, 1),
        "end_date": date(2030, 6, 30),  # 7-year compressor coverage
        "terms": "Compressor-only warranty for catastrophic failure due to manufacturing defects.",
        "attributes": {
            "coverage_type": "compressor_only",
            "labor_included": False,
            "response_time": "standard",
            "notes": "Proof of annual maintenance required for claims.",
        },
        "created_at": datetime(2023, 7, 3, 10, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2023, 7, 3, 10, 0, tzinfo=timezone.utc),
    },
    {
        "id": "d9dd0217-7e88-5dc5-9ccc-b530114c19ae",
        "asset_id": ASSET_ID,
        "vendor_id": VENDOR_ID,
        "policy_no": "WARR-HVAC-CONTROLS-004",
        "start_date": date(2023, 7, 1),
        "end_date": date(2028, 6, 30),  # 5-year controls warranty
        "terms": "Warranty on factory-supplied controls, sensors, and BAS interface components.",
        "attributes": {
            "coverage_type": "controls",
            "labor_included": False,
            "response_time": "standard",
            "notes": "Excludes field-installed third-party controls.",
        },
        "created_at": datetime(2023, 7, 4, 11, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2023, 7, 4, 11, 0, tzinfo=timezone.utc),
    },
    {
        "id": "a4bfa654-9cfd-54a5-b456-73b6b6d5c5c0",
        "asset_id": ASSET_ID,
        "vendor_id": VENDOR_ID,
        "policy_no": "WARR-HVAC-PM-005",
        "start_date": date(2023, 7, 1),
        "end_date": date(2024, 6, 30),  # 1-year PM service agreement
        "terms": "Preventive maintenance agreement including two scheduled inspections per year.",
        "attributes": {
            "coverage_type": "service_agreement",
            "labor_included": True,
            "response_time": "scheduled",
            "visits_per_year": 2,
        },
        "created_at": datetime(2023, 7, 5, 12, 0, tzinfo=timezone.utc),
        "updated_at": datetime(2023, 7, 5, 12, 0, tzinfo=timezone.utc),
    },
]


def upgrade() -> None:
    """Seed warranties with inline rows.

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
        row = {
            col.name: raw_row[col.name]
            for col in table.columns
            if col.name in raw_row
        }

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

    log.info("Inserted %s rows into %s", inserted, TABLE_NAME)


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
