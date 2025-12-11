from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0252"
down_revision = "0251"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "compliance_records"

# Inline, realistic compliance records for a single building/asset
SEED_ROWS = [
    {
        "building_id": "2fcc53b4-7367-5852-9afb-ffdecafad618",
        "asset_id": "6c7a568b-721c-523d-b5c2-ce3fd6029630",
        "record_type": "Annual Fire Safety Inspection",
        "authority": "Grimes Fire Department",
        "identifier": "FD-INS-2023-0412",
        "issued_at": "2023-04-12",
        "expires_at": "2024-04-11",
        "documents": {
            "inspection_report": "compliance/fire/FD-INS-2023-0412.pdf",
        },
        "attributes": {
            "status": "compliant",
            "findings": "Minor exit signage issue corrected on 2023-04-20.",
        },
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
        "id": "b1c10af7-4c70-5014-91d4-d6f84dee51e1",
    },
    {
        "building_id": "2fcc53b4-7367-5852-9afb-ffdecafad618",
        "asset_id": "6c7a568b-721c-523d-b5c2-ce3fd6029630",
        "record_type": "Boiler Inspection",
        "authority": "Iowa Department of Inspections, Appeals, and Licensing",
        "identifier": "BOILER-2023-1178",
        "issued_at": "2023-09-05",
        "expires_at": "2024-09-04",
        "documents": {
            "certificate": "compliance/boiler/BOILER-2023-1178_certificate.pdf",
        },
        "attributes": {
            "status": "compliant",
            "inspector": "J. Martinez",
        },
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
        "id": "dd533b80-612f-54dd-9a65-dffc3bce7ebb",
    },
    {
        "building_id": "2fcc53b4-7367-5852-9afb-ffdecafad618",
        "asset_id": "6c7a568b-721c-523d-b5c2-ce3fd6029630",
        "record_type": "Elevator Operating Permit",
        "authority": "Iowa Division of Labor",
        "identifier": "ELEV-2023-0329",
        "issued_at": "2023-03-29",
        "expires_at": "2024-03-28",
        "documents": {
            "permit": "compliance/elevator/ELEV-2023-0329_permit.pdf",
        },
        "attributes": {
            "status": "compliant",
            "inspection_company": "Midwest Elevator Services",
        },
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
        "id": "7e3b2f7b-1741-58ad-b280-969e5dcc5cbe",
    },
    {
        "building_id": "2fcc53b4-7367-5852-9afb-ffdecafad618",
        "asset_id": "6c7a568b-721c-523d-b5c2-ce3fd6029630",
        "record_type": "Asbestos Management Plan Review",
        "authority": "Iowa Department of Education",
        "identifier": "ASB-PLAN-2023-09",
        "issued_at": "2023-09-15",
        "expires_at": "2026-09-14",
        "documents": {
            "management_plan": "compliance/asbestos/ASB-PLAN-2023-09_plan.pdf",
        },
        "attributes": {
            "status": "compliant",
            "notes": "No new friable materials identified.",
        },
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
        "id": "3df738c4-6781-510e-8fc3-92f03a33c45e",
    },
    {
        "building_id": "2fcc53b4-7367-5852-9afb-ffdecafad618",
        "asset_id": "6c7a568b-721c-523d-b5c2-ce3fd6029630",
        "record_type": "Backflow Preventer Test",
        "authority": "City of Grimes Water Department",
        "identifier": "BF-TEST-2023-1101",
        "issued_at": "2023-11-01",
        "expires_at": "2024-10-31",
        "documents": {
            "test_report": "compliance/backflow/BF-TEST-2023-1101_report.pdf",
        },
        "attributes": {
            "status": "compliant",
            "tester": "Certified Backflow Services, LLC",
        },
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
        "id": "b966bd52-3e3c-56c7-9853-912704708208",
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

    # JSON/numeric/date strings are passed through and cast by SQLAlchemy/DB
    return raw


def upgrade() -> None:
    """Insert inline seed data for compliance_records."""
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
