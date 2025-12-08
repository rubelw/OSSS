from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "tutors"

SEED_ROWS = [
    {
        "id": "82cc4801-378e-47ab-9346-09d78287b3e0",
        "first_name": "Tutor1",
        "last_name": "Support",
        "subject_area": "Math",
        "email": "tutor1@dcgschools.org",
        "phone": "515-555-7001",
    },
    {
        "id": "0873156d-9fc3-44d6-9c50-be966405bf98",
        "first_name": "Tutor2",
        "last_name": "Support",
        "subject_area": "Reading",
        "email": "tutor2@dcgschools.org",
        "phone": "515-555-7002",
    },
    {
        "id": "3345c4ce-7edc-4990-a51b-7a12693bb104",
        "first_name": "Tutor3",
        "last_name": "Support",
        "subject_area": "Science",
        "email": "tutor3@dcgschools.org",
        "phone": "515-555-7003",
    },
    {
        "id": "5ea03681-3806-4165-86ae-65920b90b3ed",
        "first_name": "Tutor4",
        "last_name": "Support",
        "subject_area": "Spanish",
        "email": "tutor4@dcgschools.org",
        "phone": "515-555-7004",
    },
    {
        "id": "6c9333d4-cc18-4e6b-b3bd-bab3838d6d8d",
        "first_name": "Tutor5",
        "last_name": "Support",
        "subject_area": "Study Skills",
        "email": "tutor5@dcgschools.org",
        "phone": "515-555-7005",
    },
]


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion from inline value to appropriate DB value."""
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


def _build_name(raw_row: dict) -> str:
    """Build a full display name from first/last, with sensible fallbacks."""
    first = (raw_row.get("first_name") or "").strip()
    last = (raw_row.get("last_name") or "").strip()
    if first or last:
        return f"{first} {last}".strip()

    # Fallback: use subject_area or email if somehow first/last are missing
    if raw_row.get("subject_area"):
        return f"Tutor - {raw_row['subject_area']}"
    if raw_row.get("email"):
        return raw_row["email"]

    return "Tutor"


def upgrade() -> None:
    """Load seed data for tutors from inline SEED_ROWS.

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

        # Only include columns that actually exist on the table
        for col in table.columns:
            raw_val = None

            if col.name in raw_row:
                raw_val = raw_row[col.name]
            elif col.name == "name":
                # Derive the NOT NULL name column from first/last/subject/email
                raw_val = _build_name(raw_row)
            else:
                # Let server defaults handle timestamps, etc.
                continue

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

    log.info(
        "Inserted %s rows into %s from inline seed data",
        inserted,
        TABLE_NAME,
    )


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
