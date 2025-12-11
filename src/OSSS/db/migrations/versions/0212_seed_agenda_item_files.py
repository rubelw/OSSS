from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0212"
down_revision = "0211"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "agenda_item_files"
CSV_FILE = None  # no longer used; seeding inline instead

# Inline seed rows with realistic values
# Columns:
#   created_at, updated_at, id, agenda_item_id, file_id, caption
SEED_ROWS = [
    {
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
        "id": "555a0e60-5d13-559a-860c-12d88558d20e",
        "agenda_item_id": "ca321d07-eec1-539e-a9f4-17f7d2533683",
        "file_id": "39ca63db-2221-5408-ad28-c6dfaac3056d",
        "caption": "Board packet cover page and meeting overview",
    },
    {
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
        "id": "de3518b5-0e81-5184-8075-56eec6b6d6e2",
        "agenda_item_id": "ca321d07-eec1-539e-a9f4-17f7d2533683",
        "file_id": "39ca63db-2221-5408-ad28-c6dfaac3056d",
        "caption": "Draft agenda for January regular board meeting",
    },
    {
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
        "id": "5866aeaa-5762-54b6-bda0-27975dbaced4",
        "agenda_item_id": "ca321d07-eec1-539e-a9f4-17f7d2533683",
        "file_id": "39ca63db-2221-5408-ad28-c6dfaac3056d",
        "caption": "Board norms and meeting procedures handout",
    },
    {
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
        "id": "c3a74e92-684d-5322-a481-a49b9c2eece8",
        "agenda_item_id": "ca321d07-eec1-539e-a9f4-17f7d2533683",
        "file_id": "39ca63db-2221-5408-ad28-c6dfaac3056d",
        "caption": "Roll call and quorum verification checklist",
    },
    {
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
        "id": "13a13a9e-bf22-5ce3-8327-376f4b938ee9",
        "agenda_item_id": "ca321d07-eec1-539e-a9f4-17f7d2533683",
        "file_id": "39ca63db-2221-5408-ad28-c6dfaac3056d",
        "caption": "Procedures for adopting and amending the agenda",
    },
]


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion from inline values to appropriate Python/DB values."""
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

    # Otherwise, pass raw through and let DB cast (UUID, JSON, ints, etc.)
    return raw


def upgrade() -> None:
    """Load seed data for agenda_item_files from inline SEED_ROWS.

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

    rows = SEED_ROWS
    if not rows:
        log.info("No inline seed rows defined for %s", TABLE_NAME)
        return

    inserted = 0
    for raw_row in rows:
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

    log.info("Inserted %s inline seed rows into %s", inserted, TABLE_NAME)


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
