from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0125_3"
down_revision = "0125_2"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "curriculum_units"

# Inline seed data derived from the provided rows
ROWS = [
    {
        "curriculum_id": "7f2fff69-6623-5c5c-8038-0c9afeb4dd85",
        "title": "curriculum_units_title_1",
        "order_index": 1,
        "summary": "curriculum_units_summary_1",
        "metadata": {},
        "id": "cc885492-4e2f-5a5c-89f1-bd06ef5dd38a",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
    },
    {
        "curriculum_id": "7f2fff69-6623-5c5c-8038-0c9afeb4dd85",
        "title": "curriculum_units_title_2",
        "order_index": 2,
        "summary": "curriculum_units_summary_2",
        "metadata": {},
        "id": "c865194f-416c-5639-ab31-0168d1aea2ce",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
    },
    {
        "curriculum_id": "7f2fff69-6623-5c5c-8038-0c9afeb4dd85",
        "title": "curriculum_units_title_3",
        "order_index": 3,
        "summary": "curriculum_units_summary_3",
        "metadata": {},
        "id": "2107beaa-0569-58fe-8822-72d051dbfa08",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
    },
    {
        "curriculum_id": "7f2fff69-6623-5c5c-8038-0c9afeb4dd85",
        "title": "curriculum_units_title_4",
        "order_index": 4,
        "summary": "curriculum_units_summary_4",
        "metadata": {},
        "id": "e2f5f0df-128c-5360-949d-945cdf07a9bf",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
    },
    {
        "curriculum_id": "7f2fff69-6623-5c5c-8038-0c9afeb4dd85",
        "title": "curriculum_units_title_5",
        "order_index": 5,
        "summary": "curriculum_units_summary_5",
        "metadata": {},
        "id": "30c7a47c-7004-547e-8de4-3379795b0e06",
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
    """Seed fixed curriculum_units rows inline (no CSV file)."""
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
            # col.name will include "metadata" (physical column), not "metadata_json"
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
