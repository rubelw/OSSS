from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0084"
down_revision = "0082"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "agenda_workflow_steps"

# Inline seed data
INLINE_ROWS = [
    {
        "workflow_id": "bc45163b-5dc1-5781-bf26-15e5033b83ba",
        "step_no": 1,
        "approver_type": "USER_PROFILE",
        "approver_id": "6602bacc-996f-5af2-8b26-63df0bcfc38b",
        "rule": "Building administrator initial review for completeness and alignment with school goals",
        "id": "d7ed0e4d-6351-5139-8da2-64634cdc6367",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
    },
    {
        "workflow_id": "bc45163b-5dc1-5781-bf26-15e5033b83ba",
        "step_no": 2,
        "approver_type": "USER_PROFILE",
        "approver_id": "a306d41a-ba68-5886-ac96-883eaddce6fb",
        "rule": "Superintendent approval to ensure consistency with district policies and strategic plan",
        "id": "6453613a-14d7-5137-a02e-119a106c9fc6",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
    },
    {
        "workflow_id": "bc45163b-5dc1-5781-bf26-15e5033b83ba",
        "step_no": 3,
        "approver_type": "USER_PROFILE",
        "approver_id": "49fe3298-ab5d-55ae-82e9-0a71cc2a65da",
        "rule": "Business manager review for fiscal impact, funding sources, and budget alignment",
        "id": "4b69a101-c816-5dd5-ab42-60b85d6fa91a",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
    },
    {
        "workflow_id": "bc45163b-5dc1-5781-bf26-15e5033b83ba",
        "step_no": 4,
        "approver_type": "USER_PROFILE",
        "approver_id": "2b736431-028a-57d1-9672-6e6eac16f710",
        "rule": "District cabinet/leadership team approval to confirm operational implications and readiness",
        "id": "73d1083a-5e4b-5af3-9ebf-37562cc580c4",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
    },
    {
        "workflow_id": "bc45163b-5dc1-5781-bf26-15e5033b83ba",
        "step_no": 5,
        "approver_type": "USER_PROFILE",
        "approver_id": "b2e04b9f-476d-564b-9b1c-f4d896ede948",
        "rule": "Board president final approval for placement on the formal board agenda and meeting packet",
        "id": "353babe2-c852-5358-92ae-9fa260053ecd",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
    },
]


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion from Python/inline value to appropriate DB value."""
    if raw == "" or raw is None:
        return None

    t = col.type

    # Boolean handling (kept for consistency with other seed migrations)
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

    # Otherwise, let the DB/driver handle casting
    return raw


def upgrade() -> None:
    """Insert inline seed data for agenda_workflow_steps."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(TABLE_NAME):
        log.warning("Table %s does not exist; skipping seed", TABLE_NAME)
        return

    metadata = sa.MetaData()
    table = sa.Table(TABLE_NAME, metadata, autoload_with=bind)

    if not INLINE_ROWS:
        log.info("No inline rows defined for %s; nothing to insert", TABLE_NAME)
        return

    inserted = 0
    for raw_row in INLINE_ROWS:
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

    log.info("Inserted %s inline rows into %s", inserted, TABLE_NAME)


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
