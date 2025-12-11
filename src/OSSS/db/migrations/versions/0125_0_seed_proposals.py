from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0125_0"
down_revision = "0124"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "proposals"

# Inline seed data derived from the provided CSV
ROWS = [
    {
        "organization_id": "c201e5e9-60c0-466f-8f63-aecbf868c420",
        "association_id": "313fca7d-e540-53d6-b4ae-202a33cae77b",
        "committee_id": "9f682e86-6e28-58d8-8aa7-70136e62f6e8",
        "submitted_by_id": "a09b6c88-3418-40b5-9f14-77800af409f7",
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "subject_id": "01010101-0101-4101-8101-010101010101",
        "course_id": "a4cddcde-b046-5dd4-8255-593ba99983c6",
        "title": "proposals_title_1",
        "summary": "proposals_summary_1",
        "rationale": "proposals_rationale_1",
        "status": "draft",
        "submitted_at": "2024-01-01T01:00:00Z",
        "attributes": {},
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
        "id": "96bc433b-c25c-5870-80e2-b50df1bf1d66",
    },
    {
        "organization_id": "c201e5e9-60c0-466f-8f63-aecbf868c420",
        "association_id": "6f86e1a6-a7fe-5bf8-b55c-84f1ef0f2ec9",
        "committee_id": "9f682e86-6e28-58d8-8aa7-70136e62f6e8",
        "submitted_by_id": "a09b6c88-3418-40b5-9f14-77800af409f7",
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "subject_id": "01010101-0101-4101-8101-010101010101",
        "course_id": "a4cddcde-b046-5dd4-8255-593ba99983c6",
        "title": "proposals_title_2",
        "summary": "proposals_summary_2",
        "rationale": "proposals_rationale_2",
        "status": "submitted",
        "submitted_at": "2024-01-01T02:00:00Z",
        "attributes": {},
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
        "id": "2497392e-25f8-5784-b0c9-7e46ed242dfe",
    },
    {
        "organization_id": "c201e5e9-60c0-466f-8f63-aecbf868c420",
        "association_id": "6138e272-e91c-5574-bfdd-e9db8f6dae68",
        "committee_id": "9f682e86-6e28-58d8-8aa7-70136e62f6e8",
        "submitted_by_id": "a09b6c88-3418-40b5-9f14-77800af409f7",
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "subject_id": "01010101-0101-4101-8101-010101010101",
        "course_id": "a4cddcde-b046-5dd4-8255-593ba99983c6",
        "title": "proposals_title_3",
        "summary": "proposals_summary_3",
        "rationale": "proposals_rationale_3",
        "status": "in_review",
        "submitted_at": "2024-01-01T03:00:00Z",
        "attributes": {},
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
        "id": "8ce5f006-9e4c-5546-ae2e-36f36166df11",
    },
    {
        "organization_id": "c201e5e9-60c0-466f-8f63-aecbf868c420",
        "association_id": "3c8a853b-54d2-5037-87c5-be50fd2ee14c",
        "committee_id": "9f682e86-6e28-58d8-8aa7-70136e62f6e8",
        "submitted_by_id": "a09b6c88-3418-40b5-9f14-77800af409f7",
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "subject_id": "01010101-0101-4101-8101-010101010101",
        "course_id": "a4cddcde-b046-5dd4-8255-593ba99983c6",
        "title": "proposals_title_4",
        "summary": "proposals_summary_4",
        "rationale": "proposals_rationale_4",
        "status": "approved",
        "submitted_at": "2024-01-01T04:00:00Z",
        "attributes": {},
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
        "id": "3025fe80-92e4-534b-987b-af09a478d46b",
    },
    {
        "organization_id": "c201e5e9-60c0-466f-8f63-aecbf868c420",
        "association_id": "943f6e7a-918f-5ad9-a1e4-d5ab23a37d4c",
        "committee_id": "9f682e86-6e28-58d8-8aa7-70136e62f6e8",
        "submitted_by_id": "a09b6c88-3418-40b5-9f14-77800af409f7",
        "school_id": "af33eba3-d881-554e-9b43-2a7ea376e1f0",
        "subject_id": "01010101-0101-4101-8101-010101010101",
        "course_id": "a4cddcde-b046-5dd4-8255-593ba99983c6",
        "title": "proposals_title_5",
        "summary": "proposals_summary_5",
        "rationale": "proposals_rationale_5",
        "status": "rejected",
        "submitted_at": "2024-01-01T05:00:00Z",
        "attributes": {},
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
        "id": "b55db8e9-a3c5-5bf3-8c82-91c5e4433a1d",
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

    # Let the DB handle casting for GUID, dates, timestamptz, numerics, enums, etc.
    return raw


def upgrade() -> None:
    """Seed fixed proposals rows inline (no CSV file)."""
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
