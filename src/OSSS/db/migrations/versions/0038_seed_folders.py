from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0038"
down_revision = "0037"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "folders"

# Inline seed data for folders
# Matches Folder model + timestamps:
#   org_id, parent_id, name, is_public, sort_order, id, created_at, updated_at
SEED_ROWS = [
    {
        "org_id": "c201e5e9-60c0-466f-8f63-aecbf868c420",
        "parent_id": "ddb4dbb8-0e10-5154-af81-02102d97bbb3",
        "name": "folders_name_1",
        "is_public": "false",
        "sort_order": 1,
        "id": "ddb4dbb8-0e10-5154-af81-02102d97bbb3",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
    },
    {
        "org_id": "c201e5e9-60c0-466f-8f63-aecbf868c420",
        "parent_id": "152a387f-8ab3-530c-b6ab-7d9147a59b70",
        "name": "folders_name_2",
        "is_public": "true",
        "sort_order": 2,
        "id": "152a387f-8ab3-530c-b6ab-7d9147a59b70",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
    },
    {
        "org_id": "c201e5e9-60c0-466f-8f63-aecbf868c420",
        "parent_id": "d44512d8-fea3-5437-a886-e2ecfd7aff78",
        "name": "folders_name_3",
        "is_public": "false",
        "sort_order": 3,
        "id": "d44512d8-fea3-5437-a886-e2ecfd7aff78",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
    },
    {
        "org_id": "c201e5e9-60c0-466f-8f63-aecbf868c420",
        "parent_id": "1d81f47d-8da6-5651-aec5-1f283a8f8131",
        "name": "folders_name_4",
        "is_public": "true",
        "sort_order": 4,
        "id": "1d81f47d-8da6-5651-aec5-1f283a8f8131",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
    },
    {
        "org_id": "c201e5e9-60c0-466f-8f63-aecbf868c420",
        "parent_id": "a298916b-e650-59e3-bba6-d273d1f13f94",
        "name": "folders_name_5",
        "is_public": "false",
        "sort_order": 5,
        "id": "a298916b-e650-59e3-bba6-d273d1f13f94",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
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

    # Otherwise, pass raw through and let DB cast (UUID, timestamp, etc.)
    return raw


def upgrade() -> None:
    """Load seed data for folders from inline SEED_ROWS.

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
            if col.name not in raw_row:
                continue

            raw_val = raw_row[col.name]
            value = _coerce_value(col, raw_val)
            row[col.name] = value

        if not row:
            continue

        # Explicit nested transaction (SAVEPOINT)
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
