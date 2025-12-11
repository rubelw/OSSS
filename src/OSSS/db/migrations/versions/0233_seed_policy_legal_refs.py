from __future__ import annotations

import csv  # kept for consistency with other migrations, even if unused
import logging
import os

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0233"
down_revision = "0232"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "policy_legal_refs"
CSV_FILE = None  # using inline seed data instead of CSV


# Inline seed rows with realistic values
# Columns: policy_version_id, citation, url, id, created_at, updated_at
SEED_ROWS = [
    {
        # FERPA reference (student records & privacy)
        "policy_version_id": "220ea1db-70a4-506f-8039-ffe4637cea69",
        "citation": "20 U.S.C. § 1232g (FERPA) – Family Educational Rights and Privacy Act",
        "url": "https://www.ecfr.gov/current/title-34/subtitle-A/part-99",
        "id": "b2b808c0-e4e4-53c9-80eb-c1455f9dab26",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
    },
    {
        # PPRA reference (student surveys)
        "policy_version_id": "220ea1db-70a4-506f-8039-ffe4637cea69",
        "citation": "20 U.S.C. § 1232h (PPRA) – Protection of Pupil Rights Amendment",
        "url": "https://www2.ed.gov/policy/gen/guid/fpco/ppra/index.html",
        "id": "7edb0cf5-f640-5d54-b42e-59f327ba98e5",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
    },
    {
        # Title IX reference (sex discrimination)
        "policy_version_id": "220ea1db-70a4-506f-8039-ffe4637cea69",
        "citation": "20 U.S.C. § 1681 (Title IX) – Prohibition of Sex Discrimination in Education",
        "url": "https://www.ecfr.gov/current/title-34/subtitle-B/chapter-I/part-106",
        "id": "13f4f871-a562-5a1c-a906-f1ff48fd32c1",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
    },
    {
        # IDEA reference (special education)
        "policy_version_id": "220ea1db-70a4-506f-8039-ffe4637cea69",
        "citation": "20 U.S.C. § 1400 et seq. (IDEA) – Individuals with Disabilities Education Act",
        "url": "https://sites.ed.gov/idea/statute-chapter-33/subchapter-i/1400",
        "id": "72ae4e9a-f029-52cb-8653-8becaeb9cd1d",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
    },
    {
        # Example state-law reference (e.g., Iowa open meetings / education code)
        "policy_version_id": "220ea1db-70a4-506f-8039-ffe4637cea69",
        "citation": "Iowa Code § 279.8 – Board of directors, policies, rules, and regulations",
        "url": "https://www.legis.iowa.gov/docs/ico/section/279.8.pdf",
        "id": "82edaab7-9794-5e57-8ae8-4b9c2d5d5629",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
    },
]


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion from seed values to appropriate Python/DB types."""
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

    # Otherwise, pass raw through and let DB cast (UUID, timestamptz, etc.)
    return raw


def upgrade() -> None:
    """Load seed data for policy_legal_refs from inline SEED_ROWS (no CSV)."""
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

        # Explicit nested transaction (SAVEPOINT) so one bad row doesn't kill the migration
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
