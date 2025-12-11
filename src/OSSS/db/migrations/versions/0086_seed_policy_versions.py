from __future__ import annotations

import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0086"
down_revision = "0085"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "policy_versions"


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion from Python/inline values to appropriate DB values."""
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


# Inline seed data (mirrors what would normally be in policy_versions.csv)
SEED_ROWS = [
    {
        "policy_id": "59126d6a-7ad2-4b33-a56e-f5d51701d9d2",
        "version_no": 1,
        "content": (
            "Initial adoption of Policy 100: Educational Philosophy outlining the "
            "district’s core beliefs about teaching, learning, and student success."
        ),
        "effective_date": "2024-07-01",
        "supersedes_version_id": None,
        "created_by": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "id": "220ea1db-70a4-506f-8039-ffe4637cea69",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
    },
    {
        "policy_id": "af10ef1e-4e4f-4031-b3cd-273c2ff5eb0c",
        "version_no": 1,
        "content": (
            "Initial adoption of Policy 200: Board of Directors defining board roles, "
            "responsibilities, and governance structure."
        ),
        "effective_date": "2024-07-02",
        "supersedes_version_id": None,
        "created_by": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "id": "42d49a2f-61d1-5908-9513-cd1af4ddd7c4",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
    },
    {
        "policy_id": "3ed9e8e5-7f09-4da2-96dd-d5ca8aeec35d",
        "version_no": 1,
        "content": (
            "Initial adoption of Policy 300: Administration describing the "
            "superintendent’s authority and administrative organizational structure."
        ),
        "effective_date": "2024-07-03",
        "supersedes_version_id": None,
        "created_by": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "id": "15d1d84d-bacc-55d7-86b6-54c9efa654b1",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
    },
    {
        "policy_id": "dbc0bbf2-0f6c-4bd9-94f1-81092173fa0f",
        "version_no": 1,
        "content": (
            "Initial adoption of Policy 400: Staff Personnel covering hiring practices, "
            "staff expectations, and evaluation processes."
        ),
        "effective_date": "2024-07-04",
        "supersedes_version_id": None,
        "created_by": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "id": "9247d4d2-b070-56c9-a2b6-bd77a7c4c704",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
    },
    {
        "policy_id": "7bc459bd-f536-4202-ba7c-600b26248dec",
        "version_no": 1,
        "content": (
            "Initial adoption of Policy 500: Students addressing student rights, "
            "responsibilities, conduct expectations, and disciplinary procedures."
        ),
        "effective_date": "2024-07-05",
        "supersedes_version_id": None,
        "created_by": "de036046-aeed-4e84-960c-07ca8f9b99b9",
        "id": "14ece74c-7788-5f92-bf50-bcc77871466f",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
    },
]


def upgrade() -> None:
    """Load seed data for policy_versions from inline SEED_ROWS."""
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
