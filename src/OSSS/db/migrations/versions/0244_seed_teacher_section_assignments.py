from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0244"
down_revision = "0243"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "teacher_section_assignments"

# Inline seed data for teacher_section_assignments with realistic roles/timestamps.
SEED_ROWS = [
    {
        "staff_id": "5fc9fb92-5838-4969-b67a-13868e29d881",
        "section_id": "6e9f574f-c3ac-505d-baee-e525351b2788",
        "role": "Lead Teacher",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
        "id": "25d0a68a-4d1e-58e7-b368-65614ff54588",
    },
    {
        "staff_id": "5fc9fb92-5838-4969-b67a-13868e29d881",
        "section_id": "6e9f574f-c3ac-505d-baee-e525351b2788",
        "role": "Co-Teacher",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
        "id": "7f60b153-40ff-53ad-99cc-940e5f2fe1c7",
    },
    {
        "staff_id": "5fc9fb92-5838-4969-b67a-13868e29d881",
        "section_id": "6e9f574f-c3ac-505d-baee-e525351b2788",
        "role": "Paraprofessional",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
        "id": "24c2860e-5137-53fd-953b-7cfc539f4950",
    },
    {
        "staff_id": "5fc9fb92-5838-4969-b67a-13868e29d881",
        "section_id": "6e9f574f-c3ac-505d-baee-e525351b2788",
        "role": "Substitute Teacher",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
        "id": "0b00f440-b284-54e7-882c-f6bbc69fd1d4",
    },
    {
        "staff_id": "5fc9fb92-5838-4969-b67a-13868e29d881",
        "section_id": "6e9f574f-c3ac-505d-baee-e525351b2788",
        "role": "Student Teacher",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
        "id": "18a367f3-1871-515a-91a8-6695886dd383",
    },
]


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion from inline seed value to appropriate Python/DB value."""
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

    # Let the DB handle casting for UUIDs, timestamps, etc.
    return raw


def upgrade() -> None:
    """Insert inline seed data for teacher_section_assignments."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(TABLE_NAME):
        log.warning("Table %s does not exist; skipping seed", TABLE_NAME)
        return

    metadata = sa.MetaData()
    table = sa.Table(TABLE_NAME, metadata, autoload_with=bind)

    if not SEED_ROWS:
        log.info("No inline seed rows defined for %s; skipping", TABLE_NAME)
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

        # Explicit nested transaction (SAVEPOINT) so one bad row doesn't kill the migration
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
