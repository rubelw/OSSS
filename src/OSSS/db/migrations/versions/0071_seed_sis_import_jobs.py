from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0071"
down_revision = "0070"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "sis_import_jobs"

# Inline seed data for sis_import_jobs
SEED_ROWS = [
    {
        "source": "sis_import_jobs_source_1",
        "status": "success",
        "started_at": "2024-08-01T02:00:00Z",
        "finished_at": "2024-08-01T02:10:00Z",
        "counts": {},
        "error_log": "sis_import_jobs_error_log_1",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
        "id": "567b081e-954d-4872-bf0d-182a317a9a1a",
    },
    {
        "source": "sis_import_jobs_source_2",
        "status": "success",
        "started_at": "2024-08-02T02:00:00Z",
        "finished_at": "2024-08-02T02:10:00Z",
        "counts": {},
        "error_log": "sis_import_jobs_error_log_2",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
        "id": "cd956eeb-aa93-425d-a207-43f6cdddcecc",
    },
    {
        "source": "sis_import_jobs_source_3",
        "status": "success",
        "started_at": "2024-08-03T02:00:00Z",
        "finished_at": "2024-08-03T02:10:00Z",
        "counts": {},
        "error_log": "sis_import_jobs_error_log_3",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
        "id": "d6a60a38-7cc7-4c90-8fd4-2acdb3092335",
    },
    {
        "source": "sis_import_jobs_source_4",
        "status": "success",
        "started_at": "2024-08-04T02:00:00Z",
        "finished_at": "2024-08-04T02:10:00Z",
        "counts": {},
        "error_log": "sis_import_jobs_error_log_4",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
        "id": "c776ae4c-a302-4494-9016-deb13cda75f1",
    },
    {
        "source": "sis_import_jobs_source_5",
        "status": "failed",
        "started_at": "2024-08-05T02:00:00Z",
        "finished_at": "2024-08-05T02:10:00Z",
        "counts": {},
        "error_log": "sis_import_jobs_error_log_5",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
        "id": "e36819c3-e2e1-47ba-8e9c-eb42f465d967",
    },
]


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion from Python-style value to appropriate DB-bound value."""
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

    # Otherwise, pass raw through and let DB/driver cast (UUID, JSONB, timestamptz, etc.)
    return raw


def upgrade() -> None:
    """Load seed data for sis_import_jobs from inline SEED_ROWS.

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

    if not SEED_ROWS:
        log.info("No seed rows defined for %s", TABLE_NAME)
        return

    inserted = 0
    for raw_row in SEED_ROWS:
        row: dict[str, object] = {}

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

    log.info("Inserted %s rows into %s from inline SEED_ROWS", inserted, TABLE_NAME)


def downgrade() -> None:
    """Best-effort removal of the seeded sis_import_jobs rows."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(TABLE_NAME):
        log.warning("Table %s does not exist; skipping delete", TABLE_NAME)
        return

    if not SEED_ROWS:
        log.info("No seed rows defined for %s; nothing to delete", TABLE_NAME)
        return

    metadata = sa.MetaData()
    table = sa.Table(TABLE_NAME, metadata, autoload_with=bind)

    ids = [row["id"] for row in SEED_ROWS if "id" in row]
    if not ids:
        log.info("No IDs found in seed rows for %s; nothing to delete", TABLE_NAME)
        return

    bind.execute(table.delete().where(table.c.id.in_(ids)))
    log.info("Deleted %s seeded rows from %s", len(ids), TABLE_NAME)
