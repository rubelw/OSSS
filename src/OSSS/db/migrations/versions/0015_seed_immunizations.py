from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0015"
down_revision = "0014_2"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "immunizations"

# Inline seed data (realistic naming)
ROWS = [
    {
        "name": "Measles, Mumps, Rubella (MMR)",
        "code": "MMR",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
        "id": "195b7db5-23cb-4a0f-8861-01d7588f17f5",
    },
    {
        "name": "Diphtheria, Tetanus, Pertussis (DTaP)",
        "code": "DTaP",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
        "id": "2d86ece6-62da-42b7-b5d5-bdc525aae01f",
    },
    {
        "name": "Inactivated Poliovirus (IPV)",
        "code": "IPV",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
        "id": "7105a501-f0c5-4853-9334-2c0cd8ad1225",
    },
    {
        "name": "Varicella (Chickenpox)",
        "code": "VAR",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
        "id": "35e64161-2a96-4325-919f-5779cea1ca8a",
    },
    {
        "name": "Hepatitis B",
        "code": "HepB",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
        "id": "94b7ed8e-746a-45ee-929e-ae8224d36331",
    },
]


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion from inline value to appropriate DB value."""
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

    # Otherwise, pass raw through and let the DB/driver cast it
    return raw


def upgrade() -> None:
    """Seed fixed immunization lookup rows inline."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(TABLE_NAME):
        log.warning("Table %s does not exist; skipping seed", TABLE_NAME)
        return

    metadata = sa.MetaData()
    table = sa.Table(TABLE_NAME, metadata, autoload_with=bind)

    # Optional: skip if table already has data
    existing = bind.execute(sa.select(sa.func.count()).select_from(table)).scalar()
    if existing and existing > 0:
        log.info(
            "%s already has %s rows; skipping inline immunization seed",
            TABLE_NAME,
            existing,
        )
        return

    inserted = 0
    for raw_row in ROWS:
        row = {}
        # Only include columns that actually exist on the table
        for col in table.columns:
            if col.name not in raw_row:
                continue
            value = _coerce_value(col, raw_row[col.name])
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

    log.info("Inserted %s rows into %s (inline immunization seed)", inserted, TABLE_NAME)


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
