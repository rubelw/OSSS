from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0064"
down_revision = "0063"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "standards"

# Inline seed data for standards
# Columns: id, framework_id, code, description, parent_id, grade_band,
#          effective_from, effective_to, attributes, created_at, updated_at
SEED_ROWS = [
    {
        "framework_id": "91d9e3e1-aec9-4739-a952-b92ef4c571ac",
        "code": "M.K.OA.1",
        "description": "Represent addition and subtraction with objects, drawings, or equations for numbers within 10",
        "parent_id": "1f6a8a3e-3c2d-4b11-9f10-5e2a0c9b7a01",
        "grade_band": "K",
        "effective_from": "2024-07-01",
        "effective_to": "2029-06-30",
        "attributes": {},
        "id": "1f6a8a3e-3c2d-4b11-9f10-5e2a0c9b7a01",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
    },
    {
        "framework_id": "91d9e3e1-aec9-4739-a952-b92ef4c571ac",
        "code": "M.3.NBT.2",
        "description": "Fluently add and subtract within 1000 using strategies and algorithms based on place value",
        "parent_id": "2b9cd4f0-7e35-4a22-8c21-6f3b1d8c8b02",
        "grade_band": "3",
        "effective_from": "2024-07-01",
        "effective_to": "2029-06-30",
        "attributes": {},
        "id": "2b9cd4f0-7e35-4a22-8c21-6f3b1d8c8b02",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
    },
    {
        "framework_id": "2c448aeb-eea3-4f02-b0a6-b7d9dff37d44",
        "code": "ELA.2.RL.1",
        "description": "Ask and answer questions such as who, what, where, when, why, and how to demonstrate understanding of key details in a text",
        "parent_id": "3c7de5a1-8f46-4c33-9d32-7a4c2e9d9c03",
        "grade_band": "2",
        "effective_from": "2024-07-01",
        "effective_to": "2029-06-30",
        "attributes": {},
        "id": "3c7de5a1-8f46-4c33-9d32-7a4c2e9d9c03",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
    },
    {
        "framework_id": "2c448aeb-eea3-4f02-b0a6-b7d9dff37d44",
        "code": "ELA.5.W.3",
        "description": "Write narratives to develop real or imagined experiences using effective technique, descriptive details, and clear event sequences",
        "parent_id": "4d8ef6b2-9a57-4d44-8e43-8b5d3faead04",
        "grade_band": "5",
        "effective_from": "2024-07-01",
        "effective_to": "2029-06-30",
        "attributes": {},
        "id": "4d8ef6b2-9a57-4d44-8e43-8b5d3faead04",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
    },
    {
        "framework_id": "3ee01fb7-26f1-40cb-bd2c-429970d92a88",
        "code": "SCI.6.PS1.1",
        "description": "Develop models to describe the atomic composition of simple molecules and extended structures",
        "parent_id": "5e9ff7c3-ab68-4e55-9f54-9c6e40b0be05",
        "grade_band": "6-8",
        "effective_from": "2024-07-01",
        "effective_to": "2029-06-30",
        "attributes": {},
        "id": "5e9ff7c3-ab68-4e55-9f54-9c6e40b0be05",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
    },
    {
        "framework_id": "3ee01fb7-26f1-40cb-bd2c-429970d92a88",
        "code": "SCI.9.LS2.3",
        "description": "Construct an argument supported by evidence that ecosystem interactions can stabilize or change populations",
        "parent_id": "6fa008d4-bc79-4f66-8055-ad7f51c1cf06",
        "grade_band": "9-12",
        "effective_from": "2024-07-01",
        "effective_to": "2029-06-30",
        "attributes": {},
        "id": "6fa008d4-bc79-4f66-8055-ad7f51c1cf06",
        "created_at": "2024-01-01T06:00:00Z",
        "updated_at": "2024-01-01T06:00:00Z",
    },
    {
        "framework_id": "ee206926-2bbc-4f0a-a849-148e2ab1ba19",
        "code": "SS.7.CIV.1",
        "description": "Explain how the principles of democracy are reflected in local, state, and national government",
        "parent_id": "7ab119e5-cd8a-4077-9156-be8062d2d007",
        "grade_band": "6-8",
        "effective_from": "2024-07-01",
        "effective_to": "2029-06-30",
        "attributes": {},
        "id": "7ab119e5-cd8a-4077-9156-be8062d2d007",
        "created_at": "2024-01-01T07:00:00Z",
        "updated_at": "2024-01-01T07:00:00Z",
    },
    {
        "framework_id": "ee206926-2bbc-4f0a-a849-148e2ab1ba19",
        "code": "SS.10.HIST.4",
        "description": "Analyze how historical events and movements have shaped civic institutions and practices",
        "parent_id": "8bc22af6-de9b-4188-8257-cf9173e3e108",
        "grade_band": "9-12",
        "effective_from": "2024-07-01",
        "effective_to": "2029-06-30",
        "attributes": {},
        "id": "8bc22af6-de9b-4188-8257-cf9173e3e108",
        "created_at": "2024-01-01T08:00:00Z",
        "updated_at": "2024-01-01T08:00:00Z",
    },
    {
        "framework_id": "368ff208-1694-4c1b-883a-1caeb768f6ec",
        "code": "CS.6.AP.1",
        "description": "Decompose problems into smaller, manageable tasks and design algorithms to solve them",
        "parent_id": "9cd33b07-efac-4299-8358-d0a284f4f209",
        "grade_band": "6-8",
        "effective_from": "2024-07-01",
        "effective_to": "2029-06-30",
        "attributes": {},
        "id": "9cd33b07-efac-4299-8358-d0a284f4f209",
        "created_at": "2024-01-01T09:00:00Z",
        "updated_at": "2024-01-01T09:00:00Z",
    },
    {
        "framework_id": "368ff208-1694-4c1b-883a-1caeb768f6ec",
        "code": "CS.9.NI.2",
        "description": "Describe the impact of network security and data privacy on individuals and organizations",
        "parent_id": "a0e44c18-f0bd-43aa-8459-e1b39505030a",
        "grade_band": "9-12",
        "effective_from": "2024-07-01",
        "effective_to": "2029-06-30",
        "attributes": {},
        "id": "a0e44c18-f0bd-43aa-8459-e1b39505030a",
        "created_at": "2024-01-01T10:00:00Z",
        "updated_at": "2024-01-01T10:00:00Z",
    },
]


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion from Python-style value to appropriate DB-bound value."""
    if raw == "" or raw is None:
        return None

    t = col.type

    # Boolean handling (not used here, but kept for consistency)
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

    # Let DB/SQLAlchemy handle casting for dates, datetimes, UUIDs, JSONB, etc.
    return raw


def upgrade() -> None:
    """Load seed data for standards from inline SEED_ROWS.

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

    log.info("Inserted %s rows into %s from inline SEED_ROWS", inserted, TABLE_NAME)


def downgrade() -> None:
    """Best-effort removal of the seeded standards rows."""
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
