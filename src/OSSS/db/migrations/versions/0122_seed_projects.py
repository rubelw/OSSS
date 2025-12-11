from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0122"
down_revision = "0121"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "projects"

# Inline seed data derived from the provided CSV
ROWS = [
    {
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "name": "projects_name_1",
        "project_type": "projects_project_type_1",
        "status": "projects_status_1",
        "start_date": "2024-01-02",
        "end_date": "2024-01-02",
        "budget": 1,
        "description": "projects_description_1",
        "attributes": {},
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
        "id": "54bb3dda-4385-54bb-8939-0528dc95c1e2",
    },
    {
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "name": "projects_name_2",
        "project_type": "projects_project_type_2",
        "status": "projects_status_2",
        "start_date": "2024-01-03",
        "end_date": "2024-01-03",
        "budget": 2,
        "description": "projects_description_2",
        "attributes": {},
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
        "id": "0c8ca2d9-01b6-572f-83b0-dcf23826c1e6",
    },
    {
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "name": "projects_name_3",
        "project_type": "projects_project_type_3",
        "status": "projects_status_3",
        "start_date": "2024-01-04",
        "end_date": "2024-01-04",
        "budget": 3,
        "description": "projects_description_3",
        "attributes": {},
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
        "id": "f954bcfd-d9d6-5938-b87e-c8e71b3aef35",
    },
    {
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "name": "projects_name_4",
        "project_type": "projects_project_type_4",
        "status": "projects_status_4",
        "start_date": "2024-01-05",
        "end_date": "2024-01-05",
        "budget": 4,
        "description": "projects_description_4",
        "attributes": {},
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
        "id": "555505bd-b466-5d52-8632-c9283fbf1bfd",
    },
    {
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "name": "projects_name_5",
        "project_type": "projects_project_type_5",
        "status": "projects_status_5",
        "start_date": "2024-01-06",
        "end_date": "2024-01-06",
        "budget": 5,
        "description": "projects_description_5",
        "attributes": {},
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
        "id": "9e917648-6d6d-5f06-8e21-fc8dd6d9deaf",
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

    # Let the DB handle casting for GUID, dates, timestamptz, numerics, JSON, etc.
    return raw


def upgrade() -> None:
    """Seed fixed project rows inline.

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

    log.info("Inserted %s rows into %s (inline seed)", inserted, TABLE_NAME)


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
