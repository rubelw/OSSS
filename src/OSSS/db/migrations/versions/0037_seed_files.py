from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0037"
down_revision = "0036"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "files"

# Inline seed data for files
# Columns mapped to File model:
#   storage_key, filename, size, mime_type, created_by, id
# created_at / updated_at are omitted and left to TimestampMixin defaults.
SEED_ROWS = [
    {
        "storage_key": "files_storage_key_1",
        "filename": "files_filename_1",
        "size": 1,
        "mime_type": "files_mime_type_1",
        "created_by": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "id": "39ca63db-2221-5408-ad28-c6dfaac3056d",
    },
    {
        "storage_key": "files_storage_key_2",
        "filename": "files_filename_2",
        "size": 2,
        "mime_type": "files_mime_type_2",
        "created_by": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "id": "e158083b-8b0f-52a8-bd2d-e32586c91b83",
    },
    {
        "storage_key": "files_storage_key_3",
        "filename": "files_filename_3",
        "size": 3,
        "mime_type": "files_mime_type_3",
        "created_by": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "id": "104c31e7-5b1f-54cd-be40-a0e9eed83696",
    },
    {
        "storage_key": "files_storage_key_4",
        "filename": "files_filename_4",
        "size": 4,
        "mime_type": "files_mime_type_4",
        "created_by": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "id": "dd2a8e72-9ad5-52ba-9c35-df913eb4304b",
    },
    {
        "storage_key": "files_storage_key_5",
        "filename": "files_filename_5",
        "size": 5,
        "mime_type": "files_mime_type_5",
        "created_by": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "id": "3487e636-84b1-5531-ac4a-0f78cd56ad32",
    },
]


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion from inline value to appropriate DB-bound value."""
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

    # Let DB/driver handle everything else (UUID, BigInt, etc.)
    return raw


def upgrade() -> None:
    """Load seed data for files from inline SEED_ROWS.

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

        for col in table.columns:
            # Only fill columns we have explicit values for
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

    log.info("Inserted %s rows into %s from inline seed data", inserted, TABLE_NAME)


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
