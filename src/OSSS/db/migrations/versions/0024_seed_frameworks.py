from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "frameworks"

SEED_ROWS = [
    {
        "id": "91d9e3e1-aec9-4739-a952-b92ef4c571ac",
        "name": "Math Standards Framework",
        "subject": "Math",
        "grade_band": "K-5",
        "state": "IA",
    },
    {
        "id": "2c448aeb-eea3-4f02-b0a6-b7d9dff37d44",
        "name": "ELA Standards Framework",
        "subject": "ELA",
        "grade_band": "K-5",
        "state": "IA",
    },
    {
        "id": "3ee01fb7-26f1-40cb-bd2c-429970d92a88",
        "name": "Science Standards Framework",
        "subject": "Science",
        "grade_band": "6-12",
        "state": "IA",
    },
    {
        "id": "ee206926-2bbc-4f0a-a849-148e2ab1ba19",
        "name": "Social Studies Standards Framework",
        "subject": "Social Studies",
        "grade_band": "6-12",
        "state": "IA",
    },
    {
        "id": "368ff208-1694-4c1b-883a-1caeb768f6ec",
        "name": "Computer Science Standards Framework",
        "subject": "Computer Science",
        "grade_band": "6-12",
        "state": "IA",
    },
]


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion from inline value to appropriate DB value."""
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


def _generate_code(raw_row: dict) -> str:
    """
    Generate a framework 'code' from the name/subject/grade_band.
    Example: 'Math Standards Framework' -> 'MATH_STANDARDS_FRAMEWORK'
    """
    base = raw_row.get("name") or raw_row.get("subject") or "FRAMEWORK"
    code = base.upper().replace(" ", "_")
    return code


def upgrade() -> None:
    """Load seed data for frameworks from inline SEED_ROWS.

    Each row is inserted inside an explicit nested transaction (SAVEPOINT)
    so a failing row won't abort the whole migration transaction.
    """
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(TABLE_NAME):
        log.warning("Table %s does not exist; skipping seed", TABLE_NAME)
        return

    if not SEED_ROWS:
        log.info("No seed rows defined for %s; skipping", TABLE_NAME)
        return

    metadata = sa.MetaData()
    table = sa.Table(TABLE_NAME, metadata, autoload_with=bind)

    inserted = 0
    for raw_row in SEED_ROWS:
        row: dict[str, object] = {}

        for col in table.columns:
            raw_val = None

            # 1) Direct match from SEED_ROWS
            if col.name in raw_row:
                raw_val = raw_row[col.name]

            # 2) Special mapping for NOT NULL 'code'
            elif col.name == "code":
                raw_val = _generate_code(raw_row)

            # 3) Let server_defaults handle timestamps, etc.
            else:
                continue

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

    log.info(
        "Inserted %s rows into %s from inline seed data",
        inserted,
        TABLE_NAME,
    )


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
