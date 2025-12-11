from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0204"
down_revision = "0203"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "materials"

# Inline seed rows with realistic Classroom-style materials
# Columns: type, title, url, drive_file_id, payload, announcement_id, coursework_id,
#          id, created_at, updated_at
SEED_ROWS = [
    {
        "type": "DRIVE_FILE",
        "title": "Unit 1 Syllabus (PDF)",
        "url": "https://drive.google.com/file/d/1AbCdeFGhijKlmNoPqRS_tSYLLABUS/view?usp=sharing",
        "drive_file_id": "1AbCdeFGhijKlmNoPqRS_tSYLLABUS",
        "payload": {
            "mime_type": "application/pdf",
            "description": "Course overview, expectations, grading, and classroom norms.",
            "visible_to_students": True,
        },
        "announcement_id": "7a301a78-9162-5359-a608-30c583dc83db",
        "coursework_id": "ad4834b4-ecca-50ef-b359-ef9f4e862e99",
        "id": "e5286442-ee49-539b-b564-e5a4845598a7",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
    },
    {
        "type": "YOUTUBE",
        "title": "Welcome to Algebra – Course Intro Video",
        "url": "https://youtu.be/AlgebraIntro2024",
        "drive_file_id": None,
        "payload": {
            "channel_name": "DCG Math Department",
            "duration_seconds": 420,
            "captions_available": True,
        },
        "announcement_id": "7a301a78-9162-5359-a608-30c583dc83db",
        "coursework_id": "ad4834b4-ecca-50ef-b359-ef9f4e862e99",
        "id": "4289476c-1b81-5471-b194-68ff23bc9405",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
    },
    {
        "type": "LINK",
        "title": "Online Graphing Calculator",
        "url": "https://www.desmos.com/calculator",
        "drive_file_id": None,
        "payload": {
            "description": "External tool for graphing linear and quadratic functions.",
            "requires_sign_in": False,
        },
        "announcement_id": "7a301a78-9162-5359-a608-30c583dc83db",
        "coursework_id": "ad4834b4-ecca-50ef-b359-ef9f4e862e99",
        "id": "3b56af7a-12c4-5436-9f2f-b67abdd31247",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
    },
    {
        "type": "FORM",
        "title": "First Day Student Survey",
        "url": "https://docs.google.com/forms/d/1ClassSurvey2024/viewform",
        "drive_file_id": "1ClassSurvey2024",
        "payload": {
            "response_limit": None,
            "collects_emails": True,
            "description": "Student interests, technology access, and learning preferences.",
        },
        "announcement_id": "7a301a78-9162-5359-a608-30c583dc83db",
        "coursework_id": "ad4834b4-ecca-50ef-b359-ef9f4e862e99",
        "id": "f7f872f2-ee64-51d4-91e8-b6362d526e40",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
    },
    {
        "type": "DRIVE_FILE",
        "title": "Unit 1 Practice Problems",
        "url": "https://drive.google.com/file/d/1AlgebraPracticeU1/view?usp=sharing",
        "drive_file_id": "1AlgebraPracticeU1",
        "payload": {
            "mime_type": "application/vnd.google-apps.document",
            "description": "Practice problems on expressions, equations, and inequalities.",
            "answer_key_available": True,
        },
        "announcement_id": "7a301a78-9162-5359-a608-30c583dc83db",
        "coursework_id": "ad4834b4-ecca-50ef-b359-ef9f4e862e99",
        "id": "5d63fdf7-83ad-5351-944d-c16ea3d3b15f",
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

    # Otherwise, pass raw through and let DB cast (UUID, JSONB, timestamptz, etc.)
    return raw


def upgrade() -> None:
    """Load seed data for materials from inline SEED_ROWS.

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
