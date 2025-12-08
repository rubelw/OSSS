from __future__ import annotations

import logging
import re
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "consequence_types"

SEED_ROWS = [
    {
        "id": "69dd06c1-fa2c-4225-92bd-32b1d98167cf",
        "name": "Warning",
        "description": "Verbal or written warning",
        "severity_level": "low",
    },
    {
        "id": "5be32b14-93ac-40fa-86ed-b7dbfd30383b",
        "name": "Lunch detention",
        "description": "Supervised lunch detention",
        "severity_level": "low",
    },
    {
        "id": "7aa2e680-c37a-43b9-858a-1013d93f474b",
        "name": "After-school detention",
        "description": "Supervised after-school detention",
        "severity_level": "medium",
    },
    {
        "id": "d1ab9e6e-26d5-46f5-b1cf-d5d0fefa426a",
        "name": "In-school suspension",
        "description": "Removal from regular classes for a day",
        "severity_level": "high",
    },
    {
        "id": "3777e75e-f3ca-4ef2-a830-041af7c37191",
        "name": "Out-of-school suspension",
        "description": "Short-term removal from school",
        "severity_level": "high",
    },
]


def _derive_code(raw_row: dict) -> str:
    """
    Derive a short, stable code from the row.

    Prefer 'name', fall back to 'description'.
    If both are missing/empty, fall back to id or a random UUID.
    """
    base = (raw_row.get("name") or raw_row.get("description") or "").strip()

    if base:
        # UPPER_SNAKE_CASE, strip non-alphanumerics to keep it clean
        code = base.upper()
        code = re.sub(r"[^A-Z0-9]+", "_", code).strip("_")
        # Trim to something reasonable if type has a length limit;
        # here we just pick 64 as a safe-ish default.
        return code[:64]

    # Total fallback: use provided id or a random UUID
    return (raw_row.get("id") or str(uuid.uuid4()))


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion from CSV-style string to appropriate Python value."""
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
    """Load seed data for consequence_types from inline SEED_ROWS.

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
        row = {}

        for col in table.columns:
            # Ensure we always populate 'code'
            if col.name == "code":
                raw_val = raw_row.get("code")
                if not raw_val:
                    raw_val = _derive_code(raw_row)
                value = _coerce_value(col, raw_val)
                row[col.name] = value
                continue

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

    log.info(
        "Inserted %s rows into %s from inline seed data",
        inserted,
        TABLE_NAME,
    )


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
