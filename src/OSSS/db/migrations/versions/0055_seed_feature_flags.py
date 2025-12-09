from __future__ import annotations

import csv
import logging
import os

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0055"
down_revision = "0054"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "feature_flags"
CSV_FILE = os.path.join(os.path.dirname(__file__), "csv", f"{TABLE_NAME}.csv")


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion from CSV string to appropriate Python value."""
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

    # Otherwise, pass raw through and let DB cast
    return raw


def upgrade() -> None:
    """Inline seed data for feature_flags.

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

    # Inline seed rows
    rows = [
        {
            "id": "458f5e40-e8cb-5f39-9c2b-8a1149dfc966",
            "org_id": "c201e5e9-60c0-466f-8f63-aecbf868c420",
            "key": "osss.ai_agents.enabled",
            "enabled": True,
        },
        {
            "id": "8faacaa0-9fb8-57da-ac9e-a286effd247b",
            "org_id": "c201e5e9-60c0-466f-8f63-aecbf868c420",
            "key": "osss.parent_portal.enabled",
            "enabled": True,
        },
        {
            "id": "df62c65c-e153-5952-82ca-d7ded2f6279b",
            "org_id": "c201e5e9-60c0-466f-8f63-aecbf868c420",
            "key": "osss.attendance_auto_alerts.enabled",
            "enabled": True,
        },
        {
            "id": "997aa698-4d3a-54b7-a40c-d57ffb4d7603",
            "org_id": "c201e5e9-60c0-466f-8f63-aecbf868c420",
            "key": "osss.beta.facilities_work_orders",
            "enabled": False,
        },
        {
            "id": "8244f2b6-e9ca-5f9b-b0ed-83d2dfd6f383",
            "org_id": "c201e5e9-60c0-466f-8f63-aecbf868c420",
            "key": "osss.data_quality_dashboard.enabled",
            "enabled": True,
        },
    ]

    inserted = 0
    for raw_row in rows:
        # Coerce based on reflected column types (in case enabled is Boolean later)
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

    log.info("Inserted %s inline rows into %s", inserted, TABLE_NAME)


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
