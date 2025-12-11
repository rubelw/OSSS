from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0125_2"
down_revision = "0125_1"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "curriculum_versions"

# Inline seed data derived from the provided rows
ROWS = [
    {
        "curriculum_id": "7f2fff69-6623-5c5c-8038-0c9afeb4dd85",
        "version": "curriculum_versions_version_1",
        "status": "curriculum_versions_status_1",
        "submitted_at": "2024-01-01T01:00:00Z",
        "decided_at": "2024-01-01T01:00:00Z",
        "notes": "curriculum_versions_notes_1",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
        "id": "8d122c3e-38cb-5f27-a63e-facf99bd4c49",
    },
    {
        "curriculum_id": "7f2fff69-6623-5c5c-8038-0c9afeb4dd85",
        "version": "curriculum_versions_version_2",
        "status": "curriculum_versions_status_2",
        "submitted_at": "2024-01-01T02:00:00Z",
        "decided_at": "2024-01-01T02:00:00Z",
        "notes": "curriculum_versions_notes_2",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
        "id": "d8fac4ba-5583-5241-8b58-ed53427cbed3",
    },
    {
        "curriculum_id": "7f2fff69-6623-5c5c-8038-0c9afeb4dd85",
        "version": "curriculum_versions_version_3",
        "status": "curriculum_versions_status_3",
        "submitted_at": "2024-01-01T03:00:00Z",
        "decided_at": "2024-01-01T03:00:00Z",
        "notes": "curriculum_versions_notes_3",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
        "id": "1ed9e127-5819-5f5b-b290-170c399c98c0",
    },
    {
        "curriculum_id": "7f2fff69-6623-5c5c-8038-0c9afeb4dd85",
        "version": "curriculum_versions_version_4",
        "status": "curriculum_versions_status_4",
        "submitted_at": "2024-01-01T04:00:00Z",
        "decided_at": "2024-01-01T04:00:00Z",
        "notes": "curriculum_versions_notes_4",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
        "id": "7e26fc55-9b85-5dab-b119-6eed8fa8dd73",
    },
    {
        "curriculum_id": "7f2fff69-6623-5c5c-8038-0c9afeb4dd85",
        "version": "curriculum_versions_version_5",
        "status": "curriculum_versions_status_5",
        "submitted_at": "2024-01-01T05:00:00Z",
        "decided_at": "2024-01-01T05:00:00Z",
        "notes": "curriculum_versions_notes_5",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
        "id": "4ea890a7-158a-5674-9ea2-8f145eba6205",
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

    # Let the DB handle casting for other types (GUID, enums, dates, timestamptz, numerics, etc.)
    return raw


def upgrade() -> None:
    """Seed fixed curriculum_versions rows inline (no CSV file)."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(TABLE_NAME):
        log.warning("Table %s does not exist; skipping seed", TABLE_NAME)
        return

    metadata = sa.MetaData()
    table = sa.Table(TABLE_NAME, metadata, autoload_with=bind)

    inserted = 0
    for raw_row in ROWS:
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

    log.info("Inserted %s rows into %s (inline seed)", inserted, TABLE_NAME)


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
