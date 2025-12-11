from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0110"
down_revision = "0109"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "student_school_enrollments"

# Inline seed data
ROWS = [
    {
        "student_id": "d4f53e78-1012-5322-a4f3-4bca2efc51be",
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "entry_date": "2024-08-23",
        "exit_date": "2024-01-02",
        "status": "ENROLLED",
        "exit_reason": "student_school_enrollments_exit_reason_1",
        "grade_level_id": "21212121-2121-4121-8121-212121212121",
        "created_at": "2024-08-23T08:00:00Z",
        "updated_at": "2024-08-23T08:00:00Z",
        "id": "b5d48cb6-b1ff-589e-8a03-ff809c4108d7",
    },
    {
        "student_id": "c69e40d1-eeb3-5ecd-bd7d-46b2543ac349",
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "entry_date": "2024-08-23",
        "exit_date": "2024-01-03",
        "status": "ENROLLED",
        "exit_reason": "student_school_enrollments_exit_reason_2",
        "grade_level_id": "21212121-2121-4121-8121-212121212121",
        "created_at": "2024-08-23T08:00:00Z",
        "updated_at": "2024-08-23T08:00:00Z",
        "id": "e58efdc6-8e58-5d15-b0cc-a6e30c8bfe69",
    },
    {
        "student_id": "244b09b8-8606-55df-8c29-140225ec31b2",
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "entry_date": "2024-08-23",
        "exit_date": "2024-01-04",
        "status": "ENROLLED",
        "exit_reason": "student_school_enrollments_exit_reason_3",
        "grade_level_id": "21212121-2121-4121-8121-212121212121",
        "created_at": "2024-08-23T08:00:00Z",
        "updated_at": "2024-08-23T08:00:00Z",
        "id": "8d5433be-5daa-58ae-97fd-df1a259d1fd2",
    },
    {
        "student_id": "76a9f47b-bfec-5243-8de4-5988f209feb7",
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "entry_date": "2024-08-23",
        "exit_date": "2024-01-05",
        "status": "ENROLLED",
        "exit_reason": "student_school_enrollments_exit_reason_4",
        "grade_level_id": "21212121-2121-4121-8121-212121212121",
        "created_at": "2024-08-23T08:00:00Z",
        "updated_at": "2024-08-23T08:00:00Z",
        "id": "c0bb77ef-b1c0-51bd-8c2a-53906a9a6b44",
    },
    {
        "student_id": "8606c02c-5baa-5b51-9b0c-9cd1bb5fe832",
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "entry_date": "2024-08-23",
        "exit_date": "2024-01-06",
        "status": "ENROLLED",
        "exit_reason": "student_school_enrollments_exit_reason_5",
        "grade_level_id": "21212121-2121-4121-8121-212121212121",
        "created_at": "2024-08-23T08:00:00Z",
        "updated_at": "2024-08-23T08:00:00Z",
        "id": "f236729b-6cf7-5071-ba55-d96c7336f6dd",
    },
    {
        "student_id": "2b779574-bfed-556c-8ce5-9e62cc73025f",
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "entry_date": "2024-08-23",
        "exit_date": "2024-01-07",
        "status": "ENROLLED",
        "exit_reason": "student_school_enrollments_exit_reason_6",
        "grade_level_id": "21212121-2121-4121-8121-212121212121",
        "created_at": "2024-08-23T08:00:00Z",
        "updated_at": "2024-08-23T08:00:00Z",
        "id": "d74e006b-fd5c-5112-a659-874a5b824a23",
    },
    {
        "student_id": "a3eaf728-caaf-5ff6-8e3c-cd6b512df107",
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "entry_date": "2024-08-23",
        "exit_date": "2024-01-08",
        "status": "ENROLLED",
        "exit_reason": "student_school_enrollments_exit_reason_7",
        "grade_level_id": "21212121-2121-4121-8121-212121212121",
        "created_at": "2024-08-23T08:00:00Z",
        "updated_at": "2024-08-23T08:00:00Z",
        "id": "e5559257-2411-5891-b3bb-af9993c6e1ee",
    },
    {
        "student_id": "0e43dc79-c2a4-5c7d-8016-21414e6de33b",
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "entry_date": "2024-08-23",
        "exit_date": "2024-01-09",
        "status": "ENROLLED",
        "exit_reason": "student_school_enrollments_exit_reason_8",
        "grade_level_id": "21212121-2121-4121-8121-212121212121",
        "created_at": "2024-08-23T08:00:00Z",
        "updated_at": "2024-08-23T08:00:00Z",
        "id": "c6e462eb-bef6-5020-bbc3-0dac180338d2",
    },
    {
        "student_id": "938e519e-e267-5750-8a66-5042e402aee4",
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "entry_date": "2024-08-23",
        "exit_date": "2024-01-10",
        "status": "ENROLLED",
        "exit_reason": "student_school_enrollments_exit_reason_9",
        "grade_level_id": "21212121-2121-4121-8121-212121212121",
        "created_at": "2024-08-23T08:00:00Z",
        "updated_at": "2024-08-23T08:00:00Z",
        "id": "843f73c0-a04b-5ea1-bf5b-608fef804ac4",
    },
]


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion from inline value to appropriate Python/DB value."""
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

    # Otherwise, pass raw through and let the DB cast it
    return raw


def upgrade() -> None:
    """Seed fixed student_school_enrollments rows inline.

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

    inserted = 0
    for raw_row in ROWS:
        row = {}
        for col in table.columns:
            if col.name not in raw_row:
                continue
            value = _coerce_value(col, raw_row[col.name])
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

    log.info("Inserted %s rows into %s (inline seed)", inserted, TABLE_NAME)


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
