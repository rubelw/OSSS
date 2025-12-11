from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0119"
down_revision = "0118"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "kpis"

# Inline seed data derived from the provided CSV
ROWS = [
    {
        "goal_id": "475010fd-e5b0-53d4-ba80-fe79851cf581",
        "objective_id": "8fdb9139-143b-5726-9c7f-a9d0cd10758f",
        "name": "kpis_name_1",
        "unit": "kpis_unit_1",
        "target": "1",
        "baseline": "1",
        "direction": "kpis_dir",
        "id": "3f2096a2-71ff-55af-8922-524b675b6cab",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
    },
    {
        "goal_id": "475010fd-e5b0-53d4-ba80-fe79851cf581",
        "objective_id": "8fdb9139-143b-5726-9c7f-a9d0cd10758f",
        "name": "kpis_name_2",
        "unit": "kpis_unit_2",
        "target": "2",
        "baseline": "2",
        "direction": "kpis_dir",
        "id": "3c9171c6-4320-518d-82ab-809c4848bfbc",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
    },
    {
        "goal_id": "475010fd-e5b0-53d4-ba80-fe79851cf581",
        "objective_id": "8fdb9139-143b-5726-9c7f-a9d0cd10758f",
        "name": "kpis_name_3",
        "unit": "kpis_unit_3",
        "target": "3",
        "baseline": "3",
        "direction": "kpis_dir",
        "id": "a010ea97-f94a-5da0-afbc-38e0de3e262c",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
    },
    {
        "goal_id": "475010fd-e5b0-53d4-ba80-fe79851cf581",
        "objective_id": "8fdb9139-143b-5726-9c7f-a9d0cd10758f",
        "name": "kpis_name_4",
        "unit": "kpis_unit_4",
        "target": "4",
        "baseline": "4",
        "direction": "kpis_dir",
        "id": "8ca6f861-e4ec-5750-9143-675a4f05f9d3",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
    },
    {
        "goal_id": "475010fd-e5b0-53d4-ba80-fe79851cf581",
        "objective_id": "8fdb9139-143b-5726-9c7f-a9d0cd10758f",
        "name": "kpis_name_5",
        "unit": "kpis_unit_5",
        "target": "5",
        "baseline": "5",
        "direction": "kpis_dir",
        "id": "14754a43-3379-5390-b199-84e54ef5b9bb",
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

    # Let the DB cast for GUID, Float, Integer, Timestamptz, etc.
    return raw


def upgrade() -> None:
    """Seed fixed KPI rows inline.

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
