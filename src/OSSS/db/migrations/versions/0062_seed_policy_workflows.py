from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0062"
down_revision = "0061"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "policy_workflows"

# Inline seed data for policy_workflows
# Columns: id, policy_id, name, active, created_at, updated_at
SEED_ROWS = [
    {
        "policy_id": "59126d6a-7ad2-4b33-a56e-f5d51701d9d2",
        "name": "New policy adoption workflow",
        "active": True,
        "id": "00000001-0000-4000-8000-000000000001",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
    },
    {
        "policy_id": "59126d6a-7ad2-4b33-a56e-f5d51701d9d2",
        "name": "Policy review and revision workflow",
        "active": True,
        "id": "00000002-0000-4000-8000-000000000002",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
    },
    {
        "policy_id": "af10ef1e-4e4f-4031-b3cd-273c2ff5eb0c",
        "name": "New policy adoption workflow",
        "active": True,
        "id": "00000003-0000-4000-8000-000000000003",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
    },
    {
        "policy_id": "af10ef1e-4e4f-4031-b3cd-273c2ff5eb0c",
        "name": "Policy review and revision workflow",
        "active": True,
        "id": "00000004-0000-4000-8000-000000000004",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
    },
    {
        "policy_id": "3ed9e8e5-7f09-4da2-96dd-d5ca8aeec35d",
        "name": "New policy adoption workflow",
        "active": True,
        "id": "00000005-0000-4000-8000-000000000005",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
    },
    {
        "policy_id": "3ed9e8e5-7f09-4da2-96dd-d5ca8aeec35d",
        "name": "Policy review and revision workflow",
        "active": True,
        "id": "00000006-0000-4000-8000-000000000006",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
    },
    {
        "policy_id": "dbc0bbf2-0f6c-4bd9-94f1-81092173fa0f",
        "name": "New policy adoption workflow",
        "active": True,
        "id": "00000007-0000-4000-8000-000000000007",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
    },
    {
        "policy_id": "dbc0bbf2-0f6c-4bd9-94f1-81092173fa0f",
        "name": "Policy review and revision workflow",
        "active": True,
        "id": "00000008-0000-4000-8000-000000000008",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
    },
    {
        "policy_id": "7bc459bd-f536-4202-ba7c-600b26248dec",
        "name": "New policy adoption workflow",
        "active": True,
        "id": "00000009-0000-4000-8000-000000000009",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
    },
    {
        "policy_id": "7bc459bd-f536-4202-ba7c-600b26248dec",
        "name": "Policy review and revision workflow",
        "active": True,
        "id": "00000010-0000-4000-8000-000000000010",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
    },
    {
        "policy_id": "2341657a-ff89-45b2-9f92-01e7529aae4e",
        "name": "New policy adoption workflow",
        "active": True,
        "id": "00000011-0000-4000-8000-000000000011",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
    },
    {
        "policy_id": "2341657a-ff89-45b2-9f92-01e7529aae4e",
        "name": "Policy review and revision workflow",
        "active": True,
        "id": "00000012-0000-4000-8000-000000000012",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
    },
    {
        "policy_id": "9dcdc596-fedc-47ea-84a1-63d4b5fe4054",
        "name": "New policy adoption workflow",
        "active": True,
        "id": "00000013-0000-4000-8000-000000000013",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
    },
    {
        "policy_id": "9dcdc596-fedc-47ea-84a1-63d4b5fe4054",
        "name": "Policy review and revision workflow",
        "active": True,
        "id": "00000014-0000-4000-8000-000000000014",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
    },
    {
        "policy_id": "1c073bed-78e5-4615-b9f5-1a0dcec44587",
        "name": "New policy adoption workflow",
        "active": True,
        "id": "00000015-0000-4000-8000-000000000015",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
    },
    {
        "policy_id": "1c073bed-78e5-4615-b9f5-1a0dcec44587",
        "name": "Policy review and revision workflow",
        "active": True,
        "id": "00000016-0000-4000-8000-000000000016",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
    },
    {
        "policy_id": "cdc37603-dbbf-4c20-b51d-9a46965b04ed",
        "name": "New policy adoption workflow",
        "active": True,
        "id": "00000017-0000-4000-8000-000000000017",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
    },
    {
        "policy_id": "cdc37603-dbbf-4c20-b51d-9a46965b04ed",
        "name": "Policy review and revision workflow",
        "active": True,
        "id": "00000018-0000-4000-8000-000000000018",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
    },
]


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion from Python value to appropriate DB-bound value."""
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

    # Let DB/SQLAlchemy handle casting for strings, UUIDs, timestamps, etc.
    return raw


def upgrade() -> None:
    """Load seed data for policy_workflows from inline SEED_ROWS.

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

    if not SEED_ROWS:
        log.info("No seed rows defined for %s", TABLE_NAME)
        return

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

    log.info("Inserted %s rows into %s from inline SEED_ROWS", inserted, TABLE_NAME)


def downgrade() -> None:
    """Best-effort removal of the seeded policy_workflows rows."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(TABLE_NAME):
        log.warning("Table %s does not exist; skipping delete", TABLE_NAME)
        return

    if not SEED_ROWS:
        log.info("No seed rows defined for %s; nothing to delete", TABLE_NAME)
        return

    metadata = sa.MetaData()
    table = sa.Table(TABLE_NAME, metadata, autoload_with=bind)

    ids = [row["id"] for row in SEED_ROWS if "id" in row]
    if not ids:
        log.info("No IDs found in seed rows for %s; nothing to delete", TABLE_NAME)
        return

    bind.execute(table.delete().where(table.c.id.in_(ids)))
    log.info("Deleted %s seeded rows from %s", len(ids), TABLE_NAME)
