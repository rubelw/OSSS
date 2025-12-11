from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0128"
down_revision = "0127"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "document_versions"

# Inline seed data
ROWS = [
    {
        "document_id": "e0c6ecb5-af4d-5c1c-bc1b-bf266b3ba7d8",
        "version_no": 1,
        "file_id": "39ca63db-2221-5408-ad28-c6dfaac3056d",
        "checksum": "document_versions_checksum_1",
        "created_by": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "created_at": "2024-01-01T01:00:00Z",
        "published_at": "2024-01-01T01:00:00Z",
        "id": "2cc436a3-9bd2-5ebd-83da-e163e292b9ea",
        "updated_at": "2024-01-01T01:00:00Z",
    },
    {
        "document_id": "2c50591f-2cbb-5374-82e3-b7367748ddf1",
        "version_no": 2,
        "file_id": "39ca63db-2221-5408-ad28-c6dfaac3056d",
        "checksum": "document_versions_checksum_2",
        "created_by": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "created_at": "2024-01-01T02:00:00Z",
        "published_at": "2024-01-01T02:00:00Z",
        "id": "63db12d7-b744-5641-ac65-6466666bf2cf",
        "updated_at": "2024-01-01T02:00:00Z",
    },
    {
        "document_id": "bc27bcbe-cd67-5f52-8827-b13550c4f25d",
        "version_no": 3,
        "file_id": "39ca63db-2221-5408-ad28-c6dfaac3056d",
        "checksum": "document_versions_checksum_3",
        "created_by": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "created_at": "2024-01-01T03:00:00Z",
        "published_at": "2024-01-01T03:00:00Z",
        "id": "a4d04c71-8c2f-5cdd-945a-ac973cdd4430",
        "updated_at": "2024-01-01T03:00:00Z",
    },
    {
        "document_id": "b7f12d56-6436-5165-8ab0-95cb14495d11",
        "version_no": 4,
        "file_id": "39ca63db-2221-5408-ad28-c6dfaac3056d",
        "checksum": "document_versions_checksum_4",
        "created_by": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "created_at": "2024-01-01T04:00:00Z",
        "published_at": "2024-01-01T04:00:00Z",
        "id": "8ddea86a-c552-5a4c-bb9d-cdc63670e30a",
        "updated_at": "2024-01-01T04:00:00Z",
    },
    {
        "document_id": "d28d5ab0-729c-57fa-94d2-e13bd3778d46",
        "version_no": 5,
        "file_id": "39ca63db-2221-5408-ad28-c6dfaac3056d",
        "checksum": "document_versions_checksum_5",
        "created_by": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "created_at": "2024-01-01T05:00:00Z",
        "published_at": "2024-01-01T05:00:00Z",
        "id": "f7d36a80-ecf7-55df-9c31-0262ae8af0ee",
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

    # Otherwise, let the DB cast (UUID, timestamptz, numeric, etc.)
    return raw


def upgrade() -> None:
    """Seed fixed document_versions rows inline (no CSV file)."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(TABLE_NAME):
        log.warning("Table %s does not exist; skipping seed", TABLE_NAME)
        return

    metadata = sa.MetaData()
    table = sa.Table(TABLE_NAME, metadata, autoload_with=bind)

    if not ROWS:
        log.info("No inline rows for %s; skipping", TABLE_NAME)
        return

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

    log.info("Inserted %s inline rows into %s", inserted, TABLE_NAME)


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
