from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "states"

SEED_ROWS = [
    {"code": "al", "name": "Alabama"},
    {"code": "ak", "name": "Alaska"},
    {"code": "az", "name": "Arizona"},
    {"code": "ar", "name": "Arkansas"},
    {"code": "ca", "name": "California"},
    {"code": "co", "name": "Colorado"},
    {"code": "ct", "name": "Connecticut"},
    {"code": "de", "name": "Delaware"},
    {"code": "fl", "name": "Florida"},
    {"code": "ga", "name": "Georgia"},
    {"code": "hi", "name": "Hawaii"},
    {"code": "id", "name": "Idaho"},
    {"code": "il", "name": "Illinois"},
    {"code": "in", "name": "Indiana"},
    {"code": "ia", "name": "Iowa"},
    {"code": "ks", "name": "Kansas"},
    {"code": "ky", "name": "Kentucky"},
    {"code": "la", "name": "Louisiana"},
    {"code": "me", "name": "Maine"},
    {"code": "md", "name": "Maryland"},
    {"code": "ma", "name": "Massachusetts"},
    {"code": "mi", "name": "Michigan"},
    {"code": "mn", "name": "Minnesota"},
    {"code": "ms", "name": "Mississippi"},
    {"code": "mo", "name": "Missouri"},
    {"code": "mt", "name": "Montana"},
    {"code": "ne", "name": "Nebraska"},
    {"code": "nv", "name": "Nevada"},
    {"code": "nh", "name": "New Hampshire"},
    {"code": "nj", "name": "New Jersey"},
    {"code": "nm", "name": "New Mexico"},
    {"code": "ny", "name": "New York"},
    {"code": "nc", "name": "North Carolina"},
    {"code": "nd", "name": "North Dakota"},
    {"code": "oh", "name": "Ohio"},
    {"code": "ok", "name": "Oklahoma"},
    {"code": "or", "name": "Oregon"},
    {"code": "pa", "name": "Pennsylvania"},
    {"code": "ri", "name": "Rhode Island"},
    {"code": "sc", "name": "South Carolina"},
    {"code": "sd", "name": "South Dakota"},
    {"code": "tn", "name": "Tennessee"},
    {"code": "tx", "name": "Texas"},
    {"code": "ut", "name": "Utah"},
    {"code": "vt", "name": "Vermont"},
    {"code": "va", "name": "Virginia"},
    {"code": "wa", "name": "Washington"},
    {"code": "wv", "name": "West Virginia"},
    {"code": "wi", "name": "Wisconsin"},
    {"code": "wy", "name": "Wyoming"},
    {"code": "dc", "name": "District of Columbia"},
    {"code": "pr", "name": "Puerto Rico"},
    {"code": "vi", "name": "U.S. Virgin Islands"},
    {"code": "gu", "name": "Guam"},
    {"code": "as", "name": "American Samoa"},
    {"code": "mp", "name": "Northern Mariana Islands"},
]


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
    """Load seed data for states from inline SEED_ROWS.

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

    log.info("Inserted %s rows into %s from inline seed data", inserted, TABLE_NAME)


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
