from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "medications"

# Inline seed rows, using realistic names/instructions but fixed IDs/timestamps
ROWS = [
    {
        "id": "610838d2-48eb-42a6-89be-650253d65445",
        "name": "Albuterol Inhaler",
        "instructions": "2 puffs via inhaler as needed for asthma symptoms.",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
    },
    {
        "id": "a78301af-5600-498e-bb75-249735a491bf",
        "name": "Epinephrine Auto-Injector",
        "instructions": "Inject 0.3 mg in outer thigh for severe allergic reaction; call 911.",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
    },
    {
        "id": "3cbb8070-08ac-41c6-9baf-0310d9096d6f",
        "name": "Ibuprofen",
        "instructions": "200 mg by mouth every 6 hours as needed for pain; take with food.",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
    },
    {
        "id": "6622b2da-b0a4-4326-b4f6-24cba48cbcc0",
        "name": "Acetaminophen",
        "instructions": "325 mg by mouth every 4–6 hours as needed for fever or pain.",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
    },
    {
        "id": "eb6337eb-7562-4e09-a095-d2a7a9d9da60",
        "name": "Methylphenidate",
        "instructions": "10 mg by mouth once daily in the morning with water.",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
    },
]


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion from Python value to appropriate DB value."""
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

    # Otherwise, pass raw through and let DB cast (e.g. text, timestamps with defaults)
    return raw


def upgrade() -> None:
    """
    Seed the medications table with a small catalog of medication definitions.

    Model shape:

      id (UUID, PK via UUIDMixin),
      name (Text, not null),
      instructions (Text, nullable),
      created_at / updated_at (timestamps).
    """
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(TABLE_NAME):
        log.warning("Table %s does not exist; skipping seed", TABLE_NAME)
        return

    if not ROWS:
        log.info("No seed rows defined for %s; skipping", TABLE_NAME)
        return

    metadata = sa.MetaData()
    table = sa.Table(TABLE_NAME, metadata, autoload_with=bind)

    # Optional safety: if there is already data, don't double-seed
    existing = bind.execute(sa.select(sa.func.count()).select_from(table)).scalar()
    if existing and existing > 0:
        log.info(
            "%s already has %s rows; skipping inline medication seed",
            TABLE_NAME,
            existing,
        )
        return

    inserted = 0
    for raw_row in ROWS:
        row = {}

        for col in table.columns:
            if col.name not in raw_row:
                # Let server defaults handle created_at/updated_at if omitted, etc.
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

    log.info(
        "Inserted %s rows into %s from inline medication seed data",
        inserted,
        TABLE_NAME,
    )


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
