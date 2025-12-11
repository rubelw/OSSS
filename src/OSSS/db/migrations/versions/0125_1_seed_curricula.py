from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0125_1"
down_revision = "0125_0"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "curricula"

# Inline seed data derived from the provided CSV
ROWS = [
    {
        "organization_id": "c201e5e9-60c0-466f-8f63-aecbf868c420",
        "proposal_id": "96bc433b-c25c-5870-80e2-b50df1bf1d66",
        "title": "curricula_title_1",
        "subject": "curricula_subject_1",
        "grade_range": "curricula_grade_range_1",
        "description": "curricula_description_1",
        "attributes": {},
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
        "name": "curricula_name_1",
        "status": "draft",
        "published_at": "2024-01-01T01:00:00Z",
        "metadata": {},
        "id": "7f2fff69-6623-5c5c-8038-0c9afeb4dd85",
    },
    {
        "organization_id": "c201e5e9-60c0-466f-8f63-aecbf868c420",
        "proposal_id": "96bc433b-c25c-5870-80e2-b50df1bf1d66",
        "title": "curricula_title_2",
        "subject": "curricula_subject_2",
        "grade_range": "curricula_grade_range_2",
        "description": "curricula_description_2",
        "attributes": {},
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
        "name": "curricula_name_2",
        "status": "adopted",
        "published_at": "2024-01-01T02:00:00Z",
        "metadata": {},
        "id": "3620663d-b4d9-58c7-be89-4c1f32aad05e",
    },
    {
        "organization_id": "c201e5e9-60c0-466f-8f63-aecbf868c420",
        "proposal_id": "96bc433b-c25c-5870-80e2-b50df1bf1d66",
        "title": "curricula_title_3",
        "subject": "curricula_subject_3",
        "grade_range": "curricula_grade_range_3",
        "description": "curricula_description_3",
        "attributes": {},
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
        "name": "curricula_name_3",
        "status": "retired",
        "published_at": "2024-01-01T03:00:00Z",
        "metadata": {},
        "id": "38d90941-f846-5a28-918f-423bc7835597",
    },
    {
        "organization_id": "c201e5e9-60c0-466f-8f63-aecbf868c420",
        "proposal_id": "96bc433b-c25c-5870-80e2-b50df1bf1d66",
        "title": "curricula_title_4",
        "subject": "curricula_subject_4",
        "grade_range": "curricula_grade_range_4",
        "description": "curricula_description_4",
        "attributes": {},
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
        "name": "curricula_name_4",
        "status": "draft",
        "published_at": "2024-01-01T04:00:00Z",
        "metadata": {},
        "id": "b3483651-423b-57bf-8e4e-59bceba43eba",
    },
    {
        "organization_id": "c201e5e9-60c0-466f-8f63-aecbf868c420",
        "proposal_id": "96bc433b-c25c-5870-80e2-b50df1bf1d66",
        "title": "curricula_title_5",
        "subject": "curricula_subject_5",
        "grade_range": "curricula_grade_range_5",
        "description": "curricula_description_5",
        "attributes": {},
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
        "name": "curricula_name_5",
        "status": "adopted",
        "published_at": "2024-01-01T05:00:00Z",
        "metadata": {},
        "id": "3edb71be-98bb-53f3-b654-6ffe7cf436c6",
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

    # Let the DB handle casting (GUID, enums, dates, timestamptz, numerics, JSON, etc.)
    return raw


def upgrade() -> None:
    """Seed fixed curricula rows inline (no CSV file)."""
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
