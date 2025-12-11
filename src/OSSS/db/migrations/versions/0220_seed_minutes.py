from __future__ import annotations

import csv  # kept for consistency, even though we no longer read a CSV
import logging
import os

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0220"
down_revision = "0219"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "minutes"
CSV_FILE = None  # we now seed from inline data instead of a CSV file

# Columns: meeting_id, author_id, content, published_at, id, created_at, updated_at
# Using your existing meeting & author IDs, but with realistic minutes content.
SEED_ROWS = [
    {
        "meeting_id": "89ab8c9b-8c20-5b36-95db-e4e7e0a5e3b4",
        "author_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "content": (
            "Call to Order & Roll Call\n\n"
            "- The January 1, 2024 regular board meeting was called to order at 6:00 p.m.\n"
            "- Roll call was taken and a quorum was present.\n"
            "- The agenda was approved as presented on a 5–0 vote."
        ),
        "published_at": "2024-01-01T01:00:00Z",
        "id": "7b307b37-efc7-5cf8-bd97-b3c15edc589e",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
    },
    {
        "meeting_id": "89ab8c9b-8c20-5b36-95db-e4e7e0a5e3b4",
        "author_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "content": (
            "Consent Agenda\n\n"
            "- Minutes from the December 2023 regular meeting were approved.\n"
            "- Monthly financials, including activity fund and nutrition fund reports, "
            "were reviewed and approved.\n"
            "- Personnel recommendations (new hires, lane changes, and resignations) were approved."
        ),
        "published_at": "2024-01-01T02:00:00Z",
        "id": "1521afb6-502a-5dc6-9790-ce4418e2d941",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
    },
    {
        "meeting_id": "89ab8c9b-8c20-5b36-95db-e4e7e0a5e3b4",
        "author_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "content": (
            "Instruction & Student Services\n\n"
            "- The Director of Teaching & Learning provided an update on winter diagnostic "
            "assessment data and intervention plans.\n"
            "- The board reviewed progress toward the district’s literacy and math goals.\n"
            "- No formal action was taken; the item was informational only."
        ),
        "published_at": "2024-01-01T03:00:00Z",
        "id": "f28c0d7c-bf4a-5e2e-a15f-f8690acd2c14",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
    },
    {
        "meeting_id": "89ab8c9b-8c20-5b36-95db-e4e7e0a5e3b4",
        "author_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "content": (
            "Facilities & Operations\n\n"
            "- The board received an update on the high school athletic complex phase II planning.\n"
            "- Quotes for snow removal and transportation equipment repairs were reviewed and approved.\n"
            "- Administration was authorized to proceed with final design work for summer 2024 projects."
        ),
        "published_at": "2024-01-01T04:00:00Z",
        "id": "99820e13-d71b-5373-ad6f-8f82e1a1c216",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
    },
    {
        "meeting_id": "89ab8c9b-8c20-5b36-95db-e4e7e0a5e3b4",
        "author_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "content": (
            "Closing Items\n\n"
            "- The superintendent shared upcoming calendar events and legislative session timelines.\n"
            "- Board members provided brief reports from committee meetings.\n"
            "- The meeting adjourned at 8:05 p.m. The minutes were prepared by the board secretary "
            "and submitted for approval at the next regular meeting."
        ),
        "published_at": "2024-01-01T05:00:00Z",
        "id": "7e76722a-cbf3-5b38-8975-40a8e3f64613",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
    },
]


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion from inline seed values to appropriate Python/DB values."""
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
            log.warning("Invalid boolean for %s.%s: %r; using NULL", TABLE_NAME, col.name, raw)
            return None
        return bool(raw)

    # Otherwise, pass raw through and let DB cast (UUID, timestamptz, text, etc.)
    return raw


def upgrade() -> None:
    """Load seed data for minutes from inline SEED_ROWS (no CSV)."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(TABLE_NAME):
        log.warning("Table %s does not exist; skipping seed", TABLE_NAME)
        return

    metadata = sa.MetaData()
    table = sa.Table(TABLE_NAME, metadata, autoload_with=bind)

    rows = SEED_ROWS
    if not rows:
        log.info("No inline seed rows defined for %s", TABLE_NAME)
        return

    inserted = 0
    for raw_row in rows:
        row: dict[str, object] = {}

        for col in table.columns:
            if col.name not in raw_row:
                continue
            raw_val = raw_row[col.name]
            value = _coerce_value(col, raw_val)
            row[col.name] = value

        if not row:
            continue

        # Explicit nested transaction (SAVEPOINT) so a bad row doesn't kill the migration
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

    log.info("Inserted %s inline seed rows into %s", inserted, TABLE_NAME)


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
