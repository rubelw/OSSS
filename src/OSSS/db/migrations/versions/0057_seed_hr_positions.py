from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0057"
down_revision = "0056"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "hr_positions"

# Valid gl_segments IDs from 0033:
#   2b8a4b38-8e3e-41b2-b58e-9c0f1b4e0a01  (FUND)
#   3cf0de8b-5e3a-4f7c-9c65-0c08d8e2b702  (FACILITY)
#   9c8b0f24-4d92-4b7f-9b66-32b9d8f3a903  (FUNCTION)
#   7b2c1534-47d4-4b42-9a39-6a2f9a3f5e04  (PROGRAM)
#   f10b3d5f-0dd8-4b74-9a6b-bf17a8eddd05  (PROJECT)
#   6a2f7b8c-3245-4a1f-8e29-0b3c4d5e6f06  (OBJECT)

# Inline seed rows matching HRPosition model columns
SEED_ROWS = [
    {
        "title": "Superintendent",
        "department_segment_id": "9c8b0f24-4d92-4b7f-9b66-32b9d8f3a903",  # FUNCTION
        "grade": "ADMIN-01",
        "fte": "1.0",
        "attributes": "{}",
        "id": "1a77ec94-27a2-5633-99a6-e70532fb3e87",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
    },
    {
        "title": "Assistant Superintendent",
        "department_segment_id": "9c8b0f24-4d92-4b7f-9b66-32b9d8f3a903",  # FUNCTION
        "grade": "ADMIN-02",
        "fte": "1.0",
        "attributes": "{}",
        "id": "a728488b-1048-597d-953e-c92bc5ded129",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
    },
    {
        "title": "Director of Human Resources",
        "department_segment_id": "9c8b0f24-4d92-4b7f-9b66-32b9d8f3a903",  # FUNCTION
        "grade": "ADMIN-03",
        "fte": "1.0",
        "attributes": "{}",
        "id": "7eed82a0-01af-527b-9ed5-4630c9911179",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
    },
    {
        "title": "High School Principal",
        "department_segment_id": "7b2c1534-47d4-4b42-9a39-6a2f9a3f5e04",  # PROGRAM
        "grade": "ADMIN-10",
        "fte": "1.0",
        "attributes": "{}",
        "id": "45524256-afc0-50b5-a93b-6e8f906692de",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
    },
    {
        "title": "Assistant Principal (High School)",
        "department_segment_id": "7b2c1534-47d4-4b42-9a39-6a2f9a3f5e04",  # PROGRAM
        "grade": "ADMIN-11",
        "fte": "1.0",
        "attributes": "{}",
        "id": "b3717e85-8001-5632-8eaa-729e647200c0",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
    },
    {
        "title": "Middle School Principal",
        "department_segment_id": "7b2c1534-47d4-4b42-9a39-6a2f9a3f5e04",  # PROGRAM
        "grade": "ADMIN-12",
        "fte": "1.0",
        "attributes": "{}",
        "id": "3e6c5c36-3f7a-4e0c-9f6e-4f2a98b7b101",
        "created_at": "2024-01-01T06:00:00Z",
        "updated_at": "2024-01-01T06:00:00Z",
    },
    {
        "title": "Elementary School Principal",
        "department_segment_id": "7b2c1534-47d4-4b42-9a39-6a2f9a3f5e04",  # PROGRAM
        "grade": "ADMIN-13",
        "fte": "1.0",
        "attributes": "{}",
        "id": "4fdc6d3b-91e6-4a8f-a8a0-8df3b3a74f4a",
        "created_at": "2024-01-01T07:00:00Z",
        "updated_at": "2024-01-01T07:00:00Z",
    },
    {
        "title": "Classroom Teacher (High School English)",
        "department_segment_id": "7b2c1534-47d4-4b42-9a39-6a2f9a3f5e04",  # PROGRAM
        "grade": "TEACH-01",
        "fte": "1.0",
        "attributes": "{}",
        "id": "5ba8a7e5-0cf4-4bf2-8c5a-6a858c7d16fb",
        "created_at": "2024-01-01T08:00:00Z",
        "updated_at": "2024-01-01T08:00:00Z",
    },
    {
        "title": "Classroom Teacher (Middle School Math)",
        "department_segment_id": "7b2c1534-47d4-4b42-9a39-6a2f9a3f5e04",  # PROGRAM
        "grade": "TEACH-01",
        "fte": "1.0",
        "attributes": "{}",
        "id": "6e1b9a5d-67b1-4eb3-ae23-1d17bc50e803",
        "created_at": "2024-01-01T09:00:00Z",
        "updated_at": "2024-01-01T09:00:00Z",
    },
    {
        "title": "Classroom Teacher (Elementary)",
        "department_segment_id": "7b2c1534-47d4-4b42-9a39-6a2f9a3f5e04",  # PROGRAM
        "grade": "TEACH-01",
        "fte": "1.0",
        "attributes": "{}",
        "id": "7b97e4a1-80a5-4aa5-8a23-baf14f4c9b22",
        "created_at": "2024-01-01T10:00:00Z",
        "updated_at": "2024-01-01T10:00:00Z",
    },
    {
        "title": "Special Education Teacher",
        "department_segment_id": "7b2c1534-47d4-4b42-9a39-6a2f9a3f5e04",  # PROGRAM
        "grade": "SPED-01",
        "fte": "1.0",
        "attributes": "{}",
        "id": "8e6a2fdb-44d7-4f1e-86a0-02e36a9a80b3",
        "created_at": "2024-01-01T11:00:00Z",
        "updated_at": "2024-01-01T11:00:00Z",
    },
    {
        "title": "Paraprofessional (Special Education)",
        "department_segment_id": "7b2c1534-47d4-4b42-9a39-6a2f9a3f5e04",  # PROGRAM
        "grade": "SPED-02",
        "fte": "0.8",
        "attributes": "{}",
        "id": "9fbc1e2d-9c34-4f55-bb26-5d34b5b9b7aa",
        "created_at": "2024-01-01T12:00:00Z",
        "updated_at": "2024-01-01T12:00:00Z",
    },
    {
        "title": "School Counselor (High School)",
        "department_segment_id": "7b2c1534-47d4-4b42-9a39-6a2f9a3f5e04",  # PROGRAM
        "grade": "STU-SERV-01",
        "fte": "1.0",
        "attributes": "{}",
        "id": "0acdfc0c-3cda-47f5-88e2-631dc9e8f08e",
        "created_at": "2024-01-01T13:00:00Z",
        "updated_at": "2024-01-01T13:00:00Z",
    },
    {
        "title": "School Nurse",
        "department_segment_id": "7b2c1534-47d4-4b42-9a39-6a2f9a3f5e04",  # PROGRAM
        "grade": "STU-SERV-02",
        "fte": "1.0",
        "attributes": "{}",
        "id": "1b41e3b1-3ba7-4a39-88f0-b0a3e80081ad",
        "created_at": "2024-01-01T14:00:00Z",
        "updated_at": "2024-01-01T14:00:00Z",
    },
    {
        "title": "Technology Support Specialist",
        "department_segment_id": "6a2f7b8c-3245-4a1f-8e29-0b3c4d5e6f06",  # OBJECT
        "grade": "SUPPORT-01",
        "fte": "1.0",
        "attributes": "{}",
        "id": "2c883906-7d78-4bc9-a19b-4f7a85991231",
        "created_at": "2024-01-01T15:00:00Z",
        "updated_at": "2024-01-01T15:00:00Z",
    },
    {
        "title": "Custodian",
        "department_segment_id": "6a2f7b8c-3245-4a1f-8e29-0b3c4d5e6f06",  # OBJECT
        "grade": "OPS-01",
        "fte": "1.0",
        "attributes": "{}",
        "id": "3d9fe1d2-26c3-4b7a-8d3d-5a83eef98652",
        "created_at": "2024-01-01T16:00:00Z",
        "updated_at": "2024-01-01T16:00:00Z",
    },
    {
        "title": "Food Service Worker",
        "department_segment_id": "6a2f7b8c-3245-4a1f-8e29-0b3c4d5e6f06",  # OBJECT
        "grade": "FOOD-01",
        "fte": "0.75",
        "attributes": "{}",
        "id": "4e0a0c57-47db-4b7a-9b5a-0a1d38d3c8c0",
        "created_at": "2024-01-01T17:00:00Z",
        "updated_at": "2024-01-01T17:00:00Z",
    },
    {
        "title": "Bus Driver",
        "department_segment_id": "6a2f7b8c-3245-4a1f-8e29-0b3c4d5e6f06",  # OBJECT
        "grade": "TRANS-01",
        "fte": "0.8",
        "attributes": "{}",
        "id": "5f3b4a1f-6ed2-4cf9-91a7-05bd0a4a9c73",
        "created_at": "2024-01-01T18:00:00Z",
        "updated_at": "2024-01-01T18:00:00Z",
    },
    {
        "title": "Athletic Director",
        "department_segment_id": "7b2c1534-47d4-4b42-9a39-6a2f9a3f5e04",  # PROGRAM
        "grade": "ATH-01",
        "fte": "1.0",
        "attributes": "{}",
        "id": "6a94b6c1-4e95-4f39-86c3-1e2d5f5f4170",
        "created_at": "2024-01-01T19:00:00Z",
        "updated_at": "2024-01-01T19:00:00Z",
    },
]


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion from inline string values to appropriate Python/DB values."""
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

    # Otherwise, pass raw through and let DB cast (Numeric, JSONB, UUID, timestamptz, etc.)
    return raw


def upgrade() -> None:
    """Load seed data for hr_positions from inline SEED_ROWS."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(TABLE_NAME):
        log.warning("Table %s does not exist; skipping seed", TABLE_NAME)
        return

    metadata = sa.MetaData()
    table = sa.Table(TABLE_NAME, metadata, autoload_with=bind)

    if not SEED_ROWS:
        log.info("No SEED_ROWS defined for %s; skipping", TABLE_NAME)
        return

    inserted = 0
    for raw_row in SEED_ROWS:
        row: dict[str, object] = {}

        for col in table.columns:
            if col.name not in raw_row:
                continue
            raw_val = raw_row[col.name]
            row[col.name] = _coerce_value(col, raw_val)

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
    # No-op downgrade; seed data is left in place.
    pass
