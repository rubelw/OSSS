from __future__ import annotations

import csv  # kept for consistency with other migrations (unused now)
import logging
import os   # kept for consistency with other migrations (unused now)

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0149"
down_revision = "0148"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "medication_administrations"
CSV_FILE = os.path.join(os.path.dirname(__file__), "csv", f"{TABLE_NAME}.csv")  # no longer used

# Inline seed data (replaces CSV file)
ROWS = [
    {
        "student_id": "d4f53e78-1012-5322-a4f3-4bca2efc51be",
        "medication_id": "eb6337eb-7562-4e09-a095-d2a7a9d9da60",
        "administered_at": "2024-01-01T01:00:00Z",
        "dose": "medication_administrations_dose_1",
        "notes": "medication_administrations_notes_1",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
        "id": "cd5940b9-5932-5ed6-8eac-0f7945369cd1",
    },
    {
        "student_id": "d4f53e78-1012-5322-a4f3-4bca2efc51be",
        "medication_id": "eb6337eb-7562-4e09-a095-d2a7a9d9da60",
        "administered_at": "2024-01-01T02:00:00Z",
        "dose": "medication_administrations_dose_2",
        "notes": "medication_administrations_notes_2",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
        "id": "0b2dad87-c894-5470-ae87-4e70d8d3036d",
    },
    {
        "student_id": "d4f53e78-1012-5322-a4f3-4bca2efc51be",
        "medication_id": "eb6337eb-7562-4e09-a095-d2a7a9d9da60",
        "administered_at": "2024-01-01T03:00:00Z",
        "dose": "medication_administrations_dose_3",
        "notes": "medication_administrations_notes_3",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
        "id": "1306ac20-2202-5190-8be0-6be815c09b44",
    },
    {
        "student_id": "d4f53e78-1012-5322-a4f3-4bca2efc51be",
        "medication_id": "eb6337eb-7562-4e09-a095-d2a7a9d9da60",
        "administered_at": "2024-01-01T04:00:00Z",
        "dose": "medication_administrations_dose_4",
        "notes": "medication_administrations_notes_4",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
        "id": "74c38524-8b58-56ae-9490-e626297a2fd5",
    },
    {
        "student_id": "d4f53e78-1012-5322-a4f3-4bca2efc51be",
        "medication_id": "eb6337eb-7562-4e09-a095-d2a7a9d9da60",
        "administered_at": "2024-01-01T05:00:00Z",
        "dose": "medication_administrations_dose_5",
        "notes": "medication_administrations_notes_5",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
        "id": "c2aa12c9-a616-58cd-955e-4c80d0ebb760",
    },
]


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion from inline seed rows to appropriate Python value."""
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

    # Otherwise, pass raw through and let DB cast (UUID, numeric, date, timestamptz, etc.)
    return raw


def upgrade() -> None:
    """Seed fixed medication_administrations rows inline (no CSV file)."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(TABLE_NAME):
        log.warning("Table %s does not exist; skipping seed", TABLE_NAME)
        return

    metadata = sa.MetaData()
    table = sa.Table(TABLE_NAME, metadata, autoload_with=bind)

    if not ROWS:
        log.info("No inline rows for %s; skipping", TABLE_NAME)
        return

    inserted = 0
    for raw_row in ROWS:
        row: dict[str, object] = {}

        for col in table.columns:
            if col.name not in raw_row:
                continue
            row[col.name] = _coerce_value(col, raw_row[col.name])

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

    log.info("Inserted %s inline rows into %s", inserted, TABLE_NAME)


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
