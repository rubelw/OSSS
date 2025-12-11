from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0127"
down_revision = "0126"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "documents"

# Inline seed data from prompt
ROWS = [
    {
        "folder_id": "ddb4dbb8-0e10-5154-af81-02102d97bbb3",
        "title": "documents_title_1",
        "current_version_id": "",
        "is_public": "false",
        "id": "e0c6ecb5-af4d-5c1c-bc1b-bf266b3ba7d8",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
    },
    {
        "folder_id": "ddb4dbb8-0e10-5154-af81-02102d97bbb3",
        "title": "documents_title_2",
        "current_version_id": "",
        "is_public": "true",
        "id": "2c50591f-2cbb-5374-82e3-b7367748ddf1",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
    },
    {
        "folder_id": "ddb4dbb8-0e10-5154-af81-02102d97bbb3",
        "title": "documents_title_3",
        "current_version_id": "",
        "is_public": "false",
        "id": "bc27bcbe-cd67-5f52-8827-b13550c4f25d",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
    },
    {
        "folder_id": "ddb4dbb8-0e10-5154-af81-02102d97bbb3",
        "title": "documents_title_4",
        "current_version_id": "",
        "is_public": "true",
        "id": "b7f12d56-6436-5165-8ab0-95cb14495d11",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
    },
    {
        "folder_id": "ddb4dbb8-0e10-5154-af81-02102d97bbb3",
        "title": "documents_title_5",
        "current_version_id": "",
        "is_public": "false",
        "id": "d28d5ab0-729c-57fa-94d2-e13bd3778d46",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
    },
]


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion from inline seed rows to appropriate Python value."""
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

    # Otherwise, let the DB cast (GUID, timestamptz, etc.)
    return raw


def upgrade() -> None:
    """Seed fixed document rows inline (no CSV file)."""
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

        # Explicit nested transaction (SAVEPOINT) per row
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
