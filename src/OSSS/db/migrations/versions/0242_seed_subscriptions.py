from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0242"
down_revision = "0241"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "subscriptions"

# Inline seed rows: example users subscribed to a notification channel
SEED_ROWS = [
    {
        "id": "027a152b-9494-566e-be77-d0613fa894f8",
        "channel_id": "76330019-00cf-5cab-954e-505b6b74d86d",
        "principal_type": "user",
        "principal_id": "db5dd713-8921-510e-ac0c-b02e27e7c189",  # board member
        "created_at": "2024-01-01T01:00:00Z",
    },
    {
        "id": "13f4f281-8c5a-521f-b1ee-9b9d446737fc",
        "channel_id": "76330019-00cf-5cab-954e-505b6b74d86d",
        "principal_type": "user",
        "principal_id": "3b0053c0-fd87-51d4-af9c-dd4ed4ce7ad4",  # superintendent
        "created_at": "2024-01-01T02:00:00Z",
    },
    {
        "id": "5d481133-79c1-5bd4-8097-4262086d0ede",
        "channel_id": "76330019-00cf-5cab-954e-505b6b74d86d",
        "principal_type": "user",
        "principal_id": "4fcd091f-507c-5440-bb69-98cd24444a09",  # business manager
        "created_at": "2024-01-01T03:00:00Z",
    },
    {
        "id": "e4bedd37-0129-5460-a3a2-13a4eb64b40a",
        "channel_id": "76330019-00cf-5cab-954e-505b6b74d86d",
        "principal_type": "user",
        "principal_id": "b673ac9a-ad48-54ac-ab39-b6594ba770eb",  # communications director
        "created_at": "2024-01-01T04:00:00Z",
    },
    {
        "id": "216d9b57-0354-5dd2-9f7c-bbb5efcb6572",
        "channel_id": "76330019-00cf-5cab-954e-505b6b74d86d",
        "principal_type": "user",
        "principal_id": "9b5510ed-6167-5f98-8b74-62d53e8e4f73",  # IT director
        "created_at": "2024-01-01T05:00:00Z",
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
    """Insert inline seed data for subscriptions."""
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

    log.info("Inserted %s inline rows into %s", inserted, TABLE_NAME)


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
