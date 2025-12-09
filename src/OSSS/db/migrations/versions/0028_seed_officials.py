from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "officials"

SEED_ROWS = [
    {
        "id": "88456d31-3427-4443-8f46-7efd30e8848e",
        "first_name": "Official1",
        "last_name": "Referee",
        "role": "Referee",
        "sport": "Football",
        "phone": "515-555-4001",
        "email": "official1@iahsaa.org",
    },
    {
        "id": "349c0eee-c21b-4fb7-8d13-dfa7f305c1b2",
        "first_name": "Official2",
        "last_name": "Referee",
        "role": "Referee",
        "sport": "Basketball",
        "phone": "515-555-4002",
        "email": "official2@iahsaa.org",
    },
    {
        "id": "9c58adc4-ad0a-4130-b113-da09d7c914e3",
        "first_name": "Official3",
        "last_name": "Referee",
        "role": "Referee",
        "sport": "Volleyball",
        "phone": "515-555-4003",
        "email": "official3@iahsaa.org",
    },
    {
        "id": "1f6f2dbf-5619-4fe4-a851-0a1895049449",
        "first_name": "Official4",
        "last_name": "Referee",
        "role": "Referee",
        "sport": "Baseball",
        "phone": "515-555-4004",
        "email": "official4@iahsaa.org",
    },
    {
        "id": "6456ab0a-d22d-45cc-97a1-25dc2d942b03",
        "first_name": "Official5",
        "last_name": "Referee",
        "role": "Referee",
        "sport": "Soccer",
        "phone": "515-555-4005",
        "email": "official5@iahsaa.org",
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

    # Otherwise, pass raw through and let DB cast (e.g. enums, ints, dates)
    return raw


def upgrade() -> None:
    """Load seed data for officials from inline SEED_ROWS.

    Each row is inserted inside an explicit nested transaction (SAVEPOINT)
    so a failing row won't abort the whole migration transaction.
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
        row: dict[str, object] = {}

        for col in table.columns:
            raw_val = None

            # direct matches (id, maybe others if names line up)
            if col.name in raw_row:
                raw_val = raw_row[col.name]

            # Map into the new schema
            elif col.name == "name":
                first = (raw_row.get("first_name") or "").strip()
                last = (raw_row.get("last_name") or "").strip()
                full_name = f"{first} {last}".strip()
                # Fallback if somehow both are empty
                if not full_name:
                    full_name = raw_row.get("email") or f"Official-{raw_row['id'][:8]}"
                raw_val = full_name

            elif col.name == "certification":
                role = (raw_row.get("role") or "").strip()
                sport = (raw_row.get("sport") or "").strip()
                parts = [p for p in (role, sport) if p]
                raw_val = " - ".join(parts) if parts else None

            else:
                # created_at, updated_at, etc. can use server defaults
                continue

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

    log.info(
        "Inserted %s rows into %s from inline seed data",
        inserted,
        TABLE_NAME,
    )


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
