from __future__ import annotations

import logging
import uuid

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

# Inline seed rows consistent with the Medication model:
# id (UUID), name (required), instructions (optional), timestamps use DB defaults
SEED_ROWS = [
    {
        "name": "Albuterol Inhaler",
        "instructions": "2 puffs via inhaler as needed for asthma symptoms.",
    },
    {
        "name": "Epinephrine Auto-Injector",
        "instructions": "Inject 0.3 mg in outer thigh for severe allergy; call 911.",
    },
    {
        "name": "Ibuprofen",
        "instructions": "200 mg by mouth every 6 hours as needed for pain; take with food.",
    },
    {
        "name": "Acetaminophen",
        "instructions": "325 mg by mouth every 4–6 hours as needed for fever or pain.",
    },
    {
        "name": "Methylphenidate",
        "instructions": "10 mg by mouth once daily in the morning with water.",
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

    This follows the Medication model:

      id (UUID, PK via UUIDMixin),
      name (Text, not null),
      instructions (Text, nullable),
      created_at / updated_at (timestamps with server defaults).
    """
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(TABLE_NAME):
        log.warning("Table %s does not exist; skipping seed", TABLE_NAME)
        return

    if not SEED_ROWS:
        log.info("No seed rows defined for %s; skipping", TABLE_NAME)
        return

    metadata = sa.MetaData()
    table = sa.Table(TABLE_NAME, metadata, autoload_with=bind)

    inserted = 0
    for raw_row in SEED_ROWS:
        row = {}

        for col in table.columns:
            # Auto-generate UUID for id if not provided
            if col.name == "id" and "id" not in raw_row:
                raw_val = str(uuid.uuid4())
            elif col.name in raw_row:
                raw_val = raw_row[col.name]
            else:
                # Let created_at/updated_at use server defaults; skip any other missing cols
                continue

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
        "Inserted %s rows into %s from inline seed data",
        inserted,
        TABLE_NAME,
    )


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
