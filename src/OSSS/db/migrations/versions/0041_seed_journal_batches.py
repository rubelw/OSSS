from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0041"
down_revision = "0040"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "journal_batches"

# Inline seed data for journal_batches
# Matches JournalBatch model + TimestampMixin:
# created_at, updated_at, batch_no, description, source, status, posted_at, id
SEED_ROWS = [
    {
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
        "batch_no": "journal_batches_batch_no_1",
        "description": "Monthly closing entries batch 1.",
        "source": "journal_batches_source_1",
        "status": "journal_batches_",
        "posted_at": "2024-10-01T16:00:00Z",
        "id": "fd7d8eaf-38f2-476d-af02-ea9776c6b082",
    },
    {
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
        "batch_no": "journal_batches_batch_no_2",
        "description": "Monthly closing entries batch 2.",
        "source": "journal_batches_source_2",
        "status": "journal_batches_",
        "posted_at": "2024-10-02T16:00:00Z",
        "id": "ea8b5fa5-473d-416d-a816-f06ec874197e",
    },
    {
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
        "batch_no": "journal_batches_batch_no_3",
        "description": "Monthly closing entries batch 3.",
        "source": "journal_batches_source_3",
        "status": "journal_batches_",
        "posted_at": "2024-10-03T16:00:00Z",
        "id": "833eb783-96f3-4625-b43e-ba7716cad1c3",
    },
    {
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
        "batch_no": "journal_batches_batch_no_4",
        "description": "Monthly closing entries batch 4.",
        "source": "journal_batches_source_4",
        "status": "journal_batches_",
        "posted_at": "2024-10-04T16:00:00Z",
        "id": "bbce8bef-0ceb-49ba-ba67-ee02041ec47f",
    },
    {
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
        "batch_no": "journal_batches_batch_no_5",
        "description": "Monthly closing entries batch 5.",
        "source": "journal_batches_source_5",
        "status": "journal_batches_",
        "posted_at": "2024-10-05T16:00:00Z",
        "id": "5d5c9ec0-9648-4573-91bc-dfee65756371",
    },
]


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion from inline value to appropriate DB-bound value."""
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

    # Otherwise, pass raw through and let DB cast (timestamps, UUIDs, etc.)
    return raw


def upgrade() -> None:
    """Load seed data for journal_batches from inline SEED_ROWS.

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
            if col.name not in raw_row:
                # Let server defaults fill in anything not provided
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

    log.info("Inserted %s rows into %s from inline seed data", inserted, TABLE_NAME)


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
