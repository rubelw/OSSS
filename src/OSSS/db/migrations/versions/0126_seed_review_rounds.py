from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0126"
down_revision = "0125_3"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "review_rounds"

# Inline seed data from prompt
ROWS = [
    {
        "round_no": 1,
        "opened_at": "2024-01-01T01:00:00Z",
        "closed_at": "2024-01-01T01:00:00Z",
        "status": "open",
        "proposal_id": "96bc433b-c25c-5870-80e2-b50df1bf1d66",
        "id": "4f0cdda3-ce2d-5928-97e9-d20ac96daa47",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
    },
    {
        "round_no": 2,
        "opened_at": "2024-01-01T02:00:00Z",
        "closed_at": "2024-01-01T02:00:00Z",
        "status": "closed",
        "proposal_id": "96bc433b-c25c-5870-80e2-b50df1bf1d66",
        "id": "212abf9b-9751-5c16-954c-1c1ef2a53602",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
    },
    {
        "round_no": 3,
        "opened_at": "2024-01-01T03:00:00Z",
        "closed_at": "2024-01-01T03:00:00Z",
        "status": "canceled",
        "proposal_id": "96bc433b-c25c-5870-80e2-b50df1bf1d66",
        "id": "81542e6f-ca63-568e-97a2-221a0e92bd95",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
    },
    {
        "round_no": 4,
        "opened_at": "2024-01-01T04:00:00Z",
        "closed_at": "2024-01-01T04:00:00Z",
        "status": "open",
        "proposal_id": "96bc433b-c25c-5870-80e2-b50df1bf1d66",
        "id": "0ffc2535-c10a-547b-9ced-eb66953db289",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
    },
    {
        "round_no": 5,
        "opened_at": "2024-01-01T05:00:00Z",
        "closed_at": "2024-01-01T05:00:00Z",
        "status": "closed",
        "proposal_id": "96bc433b-c25c-5870-80e2-b50df1bf1d66",
        "id": "08d55fa9-449f-5cfe-8cf1-735c8b98547e",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
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
    """Seed fixed review_rounds rows inline (no CSV file)."""
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
