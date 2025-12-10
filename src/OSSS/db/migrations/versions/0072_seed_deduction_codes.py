from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0072"
down_revision = "0071"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "deduction_codes"

# Inline seed data for deduction_codes
SEED_ROWS = [
    {
        "code": "RETIRE_TSA",
        "name": "403(b) Tax-Sheltered Annuity",
        "pretax": False,
        "vendor_id": "d7b782fe-058c-4344-b6db-15c5b7348607",
        "attributes": {},
        "id": "cba98ada-b903-56a3-afc1-574d9e45e19f",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
    },
    {
        "code": "HEALTH_PRETAX",
        "name": "Health Insurance Premium",
        "pretax": True,
        "vendor_id": "d7b782fe-058c-4344-b6db-15c5b7348607",
        "attributes": {},
        "id": "f623ef4f-9b06-54ae-bb7c-6521a4bd89fa",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
    },
    {
        "code": "DENTAL_PRETAX",
        "name": "Dental Insurance Premium",
        "pretax": False,
        "vendor_id": "d7b782fe-058c-4344-b6db-15c5b7348607",
        "attributes": {},
        "id": "df36e5db-cd96-5563-bea5-40dded4755c7",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
    },
    {
        "code": "FSA_DEP",
        "name": "FSA Dependent Care",
        "pretax": True,
        "vendor_id": "d7b782fe-058c-4344-b6db-15c5b7348607",
        "attributes": {},
        "id": "d2b50dc5-a78b-5143-9a50-c8bfbf49ae0d",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
    },
    {
        "code": "UNION_DUES",
        "name": "Union Dues",
        "pretax": False,
        "vendor_id": "d7b782fe-058c-4344-b6db-15c5b7348607",
        "attributes": {},
        "id": "b0477d4f-89df-5224-80fd-d8012e2e83a9",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
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
            if v in ("true", "t", "1", "yes", "y"):
                return True
            if v in ("false", "f", "0", "no", "n"):
                return False
            log.warning("Invalid boolean for %s.%s: %r; using NULL", TABLE_NAME, col.name, raw)
            return None
        return bool(raw)

    # Otherwise, pass raw through and let DB cast
    return raw


def upgrade() -> None:
    """Load seed data for deduction_codes from inline SEED_ROWS.

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

    if not SEED_ROWS:
        log.info("No seed rows defined for %s", TABLE_NAME)
        return

    inserted = 0
    for raw_row in SEED_ROWS:
        row: dict[str, object] = {}

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

    log.info("Inserted %s rows into %s (inline seed)", inserted, TABLE_NAME)


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
