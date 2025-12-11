from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0251"
down_revision = "0250"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "leases"

# Inline seed rows with realistic lease data for a single building.
SEED_ROWS = [
    {
        "building_id": "2fcc53b4-7367-5852-9afb-ffdecafad618",
        "landlord": "Grimes Community School District",
        "tenant": "Grimes Parks and Recreation Department",
        "start_date": "2023-07-01",
        "end_date": "2024-06-30",
        "base_rent": 1500.00,
        "rent_schedule": {
            "frequency": "monthly",
            "due_day": 1,
            "escalation_percent_per_year": 2.0,
        },
        "options": {
            "renewal_terms": "One 12-month renewal option with 60 days written notice."
        },
        "documents": {
            "lease_pdf": "leases/2023/gym_evening_use.pdf",
            "insurance_certificate": "insurance/parks_rec_2023_2024.pdf",
        },
        "attributes": {
            "internal_reference": "LS-2023-001",
            "use": "Shared gym space for evening recreation programs",
        },
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
        "id": "afbd63c7-d42f-54b3-bc53-b1df594e19bc",
    },
    {
        "building_id": "2fcc53b4-7367-5852-9afb-ffdecafad618",
        "landlord": "Grimes Community School District",
        "tenant": "Central Iowa Youth Basketball Association",
        "start_date": "2023-08-15",
        "end_date": "2025-05-31",
        "base_rent": 1200.00,
        "rent_schedule": {
            "frequency": "monthly",
            "due_day": 15,
            "escalation_percent_per_year": 1.5,
        },
        "options": {
            "renewal_terms": "Option to renew for one additional season subject to board approval."
        },
        "documents": {
            "lease_pdf": "leases/2023/youth_basketball_gym_use.pdf",
        },
        "attributes": {
            "internal_reference": "LS-2023-002",
            "use": "Weekend and evening gym reservations for youth league games",
        },
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
        "id": "91664671-acc4-55c8-a511-3f04687d973a",
    },
    {
        "building_id": "2fcc53b4-7367-5852-9afb-ffdecafad618",
        "landlord": "Grimes Community School District",
        "tenant": "Community Health Outreach Clinic",
        "start_date": "2022-01-01",
        "end_date": "2026-12-31",
        "base_rent": 2500.00,
        "rent_schedule": {
            "frequency": "monthly",
            "due_day": 1,
            "escalation_percent_per_year": 3.0,
        },
        "options": {
            "renewal_terms": "Two 3-year renewal options at market rate.",
            "termination_clause": "Either party may terminate with 180 days written notice.",
        },
        "documents": {
            "lease_pdf": "leases/2022/clinic_wing_suite_101.pdf",
            "addendum": "leases/2022/clinic_maintenance_addendum.pdf",
        },
        "attributes": {
            "internal_reference": "LS-2022-004",
            "use": "Clinic space in former administrative wing",
        },
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
        "id": "b741f600-c3cb-55f8-b3be-496606122df7",
    },
    {
        "building_id": "2fcc53b4-7367-5852-9afb-ffdecafad618",
        "landlord": "Grimes Community School District",
        "tenant": "After-School Childcare Cooperative",
        "start_date": "2023-08-15",
        "end_date": "2024-06-07",
        "base_rent": 900.00,
        "rent_schedule": {
            "frequency": "monthly",
            "due_day": 5,
            "escalation_percent_per_year": 0.0,
        },
        "options": {
            "renewal_terms": "Renewable each school year upon successful performance review.",
        },
        "documents": {
            "lease_pdf": "leases/2023/after_school_program_classroom_lease.pdf",
        },
        "attributes": {
            "internal_reference": "LS-2023-007",
            "use": "Single classroom and storage space for after-school care",
        },
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
        "id": "20af8592-c01e-51e0-b100-ee97fd4a125b",
    },
    {
        "building_id": "2fcc53b4-7367-5852-9afb-ffdecafad618",
        "landlord": "Grimes Community School District",
        "tenant": "Booster Club Concessions",
        "start_date": "2023-08-01",
        "end_date": "2025-07-31",
        "base_rent": 500.00,
        "rent_schedule": {
            "frequency": "seasonal",
            "billing_periods_per_year": 2,
            "due_dates": ["2023-08-15", "2023-11-15"],
        },
        "options": {
            "revenue_share": "10% of net concession revenue in lieu of higher base rent.",
        },
        "documents": {
            "lease_pdf": "leases/2023/concessions_stand_use_agreement.pdf",
        },
        "attributes": {
            "internal_reference": "LS-2023-009",
            "use": "Concession stand and storage during home events",
        },
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
        "id": "cfa8614a-e4d3-56a4-afcb-3ee478a6c4cb",
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

    # JSON / dict / numeric / date strings are passed through and
    # allowed to be cast by SQLAlchemy / the DB driver.
    return raw


def upgrade() -> None:
    """Insert inline seed data for leases."""
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
