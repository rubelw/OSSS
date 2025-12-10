from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0061"
down_revision = "0060"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "policies"

# Inline seed data for policies
# Matches Policy model: id, org_id, code, title, status
SEED_ROWS = [
    {
        "id": "59126d6a-7ad2-4b33-a56e-f5d51701d9d2",
        "org_id": "c201e5e9-60c0-466f-8f63-aecbf868c420",
        "code": "100",
        "title": "Educational Philosophy",
        "status": "active",
    },
    {
        "id": "af10ef1e-4e4f-4031-b3cd-273c2ff5eb0c",
        "org_id": "c201e5e9-60c0-466f-8f63-aecbf868c420",
        "code": "200",
        "title": "Board of Directors",
        "status": "active",
    },
    {
        "id": "3ed9e8e5-7f09-4da2-96dd-d5ca8aeec35d",
        "org_id": "c201e5e9-60c0-466f-8f63-aecbf868c420",
        "code": "300",
        "title": "Administration",
        "status": "active",
    },
    {
        "id": "dbc0bbf2-0f6c-4bd9-94f1-81092173fa0f",
        "org_id": "c201e5e9-60c0-466f-8f63-aecbf868c420",
        "code": "400",
        "title": "Staff Personnel",
        "status": "active",
    },
    {
        "id": "7bc459bd-f536-4202-ba7c-600b26248dec",
        "org_id": "c201e5e9-60c0-466f-8f63-aecbf868c420",
        "code": "500",
        "title": "Students",
        "status": "active",
    },
    {
        "id": "2341657a-ff89-45b2-9f92-01e7529aae4e",
        "org_id": "c201e5e9-60c0-466f-8f63-aecbf868c420",
        "code": "600",
        "title": "Educational Program",
        "status": "active",
    },
    {
        "id": "9dcdc596-fedc-47ea-84a1-63d4b5fe4054",
        "org_id": "c201e5e9-60c0-466f-8f63-aecbf868c420",
        "code": "700",
        "title": "Non-Instructional Operations and Business Services",
        "status": "active",
    },
    {
        "id": "1c073bed-78e5-4615-b9f5-1a0dcec44587",
        "org_id": "c201e5e9-60c0-466f-8f63-aecbf868c420",
        "code": "800",
        "title": "Buildings and Sites",
        "status": "active",
    },
    {
        "id": "cdc37603-dbbf-4c20-b51d-9a46965b04ed",
        "org_id": "c201e5e9-60c0-466f-8f63-aecbf868c420",
        "code": "1000",
        "title": "School–Community Relations",
        "status": "active",
    },
]


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion from Python value to appropriate DB-bound value."""
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

    # Strings, UUIDs, JSON/dicts, etc. are passed through and cast by SQLAlchemy/DB
    return raw


def upgrade() -> None:
    """Load seed data for policies from inline SEED_ROWS.

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

    log.info("Inserted %s rows into %s from inline SEED_ROWS", inserted, TABLE_NAME)


def downgrade() -> None:
    """Best-effort removal of the seeded policies rows."""
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
