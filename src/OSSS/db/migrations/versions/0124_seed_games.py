from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0124"
down_revision = "0123"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "games"

# Inline seed data derived from the provided CSV
ROWS = [
    {
        "team_id": "ee268bc5-47ec-59b2-b5bb-00492928ca1f",
        "opponent": "games_opponent_1",
        "score": 1,
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
        "season_id": "c39ad8bc-6fea-4025-9a5f-d1887a04fe6c",
        "id": "35b62837-a339-5111-aa05-37dfbcebd7e7",
    },
    {
        "team_id": "ee268bc5-47ec-59b2-b5bb-00492928ca1f",
        "opponent": "games_opponent_2",
        "score": 2,
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
        "season_id": "c39ad8bc-6fea-4025-9a5f-d1887a04fe6c",
        "id": "e26e0d46-0ce1-532b-9e2b-b87cef6b3f0c",
    },
    {
        "team_id": "ee268bc5-47ec-59b2-b5bb-00492928ca1f",
        "opponent": "games_opponent_3",
        "score": 3,
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
        "season_id": "c39ad8bc-6fea-4025-9a5f-d1887a04fe6c",
        "id": "967495c0-eebf-5020-be2f-68da36ed271c",
    },
    {
        "team_id": "ee268bc5-47ec-59b2-b5bb-00492928ca1f",
        "opponent": "games_opponent_4",
        "score": 4,
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
        "season_id": "c39ad8bc-6fea-4025-9a5f-d1887a04fe6c",
        "id": "c0c842a7-9ea7-576b-8704-9bfb987480bd",
    },
    {
        "team_id": "ee268bc5-47ec-59b2-b5bb-00492928ca1f",
        "opponent": "games_opponent_5",
        "score": 5,
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
        "season_id": "c39ad8bc-6fea-4025-9a5f-d1887a04fe6c",
        "id": "e30f6e61-5c31-5586-bba4-628f71c32c76",
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

    # Let the DB handle casting for GUID, dates, timestamptz, numerics, etc.
    return raw


def upgrade() -> None:
    """Seed fixed games rows inline.

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

    log.info("Inserted %s rows into %s (inline seed)", inserted, TABLE_NAME)


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
