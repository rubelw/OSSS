from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0213"
down_revision = "0212"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "agenda_item_approvals"
CSV_FILE = None  # no longer used; we seed inline instead

# Inline seed rows with realistic values
# Columns:
#   item_id, step_id, approver_id, decision, decided_at, comment,
#   id, created_at, updated_at
SEED_ROWS = [
    {
        "item_id": "ca321d07-eec1-539e-a9f4-17f7d2533683",
        "step_id": "d7ed0e4d-6351-5139-8da2-64634cdc6367",
        "approver_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "decision": "approved",
        "decided_at": "2024-01-01T01:00:00Z",
        "comment": "Reviewed and recommended for inclusion on the consent agenda.",
        "id": "e11f912f-fdd1-52ee-8578-f46a3c545a12",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
    },
    {
        "item_id": "ca321d07-eec1-539e-a9f4-17f7d2533683",
        "step_id": "d7ed0e4d-6351-5139-8da2-64634cdc6367",
        "approver_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "decision": "approved",
        "decided_at": "2024-01-01T02:00:00Z",
        "comment": "Financial impact verified by business office.",
        "id": "9db16deb-7a19-58dc-ae5a-49632131a0b2",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
    },
    {
        "item_id": "ca321d07-eec1-539e-a9f4-17f7d2533683",
        "step_id": "d7ed0e4d-6351-5139-8da2-64634cdc6367",
        "approver_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "decision": "approved",
        "decided_at": "2024-01-01T03:00:00Z",
        "comment": "Legal review completed; no policy conflicts identified.",
        "id": "e903fb2a-bd5e-5f59-a529-ad5c794e31ba",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
    },
    {
        "item_id": "ca321d07-eec1-539e-a9f4-17f7d2533683",
        "step_id": "d7ed0e4d-6351-5139-8da2-64634cdc6367",
        "approver_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "decision": "approved",
        "decided_at": "2024-01-01T04:00:00Z",
        "comment": "Superintendent approval – ready for board action.",
        "id": "6bc85d2a-e42e-5510-9ced-0912f554a19a",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
    },
    {
        "item_id": "ca321d07-eec1-539e-a9f4-17f7d2533683",
        "step_id": "d7ed0e4d-6351-5139-8da2-64634cdc6367",
        "approver_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "decision": "approved",
        "decided_at": "2024-01-01T05:00:00Z",
        "comment": "Board president confirmed item placement on the agenda.",
        "id": "2b84fec0-a548-5a3c-8427-c86ba7b7f8a7",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
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
    """Load seed data for agenda_item_approvals from inline SEED_ROWS.

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
