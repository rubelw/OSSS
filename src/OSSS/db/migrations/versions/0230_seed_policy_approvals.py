from __future__ import annotations

import csv  # kept for consistency with other migrations, even if unused
import logging
import os

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0230"
down_revision = "0229"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "policy_approvals"
CSV_FILE = None  # seeding from inline data instead of CSV


# Inline seed data with realistic values
# Columns: policy_version_id, step_id, approver_id, decision, decided_at, comment,
#          id, created_at, updated_at
SEED_ROWS = [
    {
        "policy_version_id": "220ea1db-70a4-506f-8039-ffe4637cea69",
        "step_id": "154e1730-6b50-580f-a484-9d19066d9176",
        "approver_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "decision": "approved",
        "decided_at": "2024-01-01T01:00:00Z",
        "comment": "Approved after initial policy committee review.",
        "id": "1a8c9d43-8875-5c16-a6c3-213234950546",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
    },
    {
        "policy_version_id": "220ea1db-70a4-506f-8039-ffe4637cea69",
        "step_id": "154e1730-6b50-580f-a484-9d19066d9176",
        "approver_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "decision": "approved",
        "decided_at": "2024-01-01T02:00:00Z",
        "comment": "Final language verified against state guidance.",
        "id": "f6696d66-4e4d-5fce-a800-2d6f48a9ce41",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
    },
    {
        "policy_version_id": "220ea1db-70a4-506f-8039-ffe4637cea69",
        "step_id": "154e1730-6b50-580f-a484-9d19066d9176",
        "approver_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "decision": "changes_needed",  # <= 16 chars, fits sa.String(16)
        "decided_at": "2024-01-01T03:00:00Z",
        "comment": "Requested clarification on reporting procedures.",
        "id": "2e386525-ca1c-5bff-b89c-c9f0832f7674",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
    },
    {
        "policy_version_id": "220ea1db-70a4-506f-8039-ffe4637cea69",
        "step_id": "154e1730-6b50-580f-a484-9d19066d9176",
        "approver_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "decision": "rejected",
        "decided_at": "2024-01-01T04:00:00Z",
        "comment": "Rejected due to inconsistency with existing board policy.",
        "id": "ce43d596-0fc5-5621-9d33-e03828898bf8",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
    },
    {
        "policy_version_id": "220ea1db-70a4-506f-8039-ffe4637cea69",
        "step_id": "154e1730-6b50-580f-a484-9d19066d9176",
        "approver_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "decision": "approved",
        "decided_at": "2024-01-01T05:00:00Z",
        "comment": "Approved after revisions and legal counsel review.",
        "id": "d2b8d360-47c4-5516-8327-32051f591f8c",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
    },
]


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion from seed values to appropriate Python/DB types."""
    if raw == "" or raw is None:
        return None

    t = col.type

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

    return raw


def upgrade() -> None:
    """Load seed data for policy_approvals from inline SEED_ROWS (no CSV)."""
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
