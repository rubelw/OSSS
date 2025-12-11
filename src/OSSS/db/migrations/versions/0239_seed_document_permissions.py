from __future__ import annotations

import csv
import logging
import os

from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError, DataError, StatementError

# ---- Alembic identifiers ----
revision = "0239"
down_revision = "0238"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TABLE_NAME = "document_permissions"

# Inline realistic seed data for ACL-style permissions on a board packet document.
#
# Columns:
#   created_at, updated_at, id, resource_type, resource_id,
#   principal_type, principal_id, permission
#
# Scenario:
# - A January 2024 board packet document.
# - The superintendent has manage access.
# - The board secretary can edit.
# - The "Board Members" group can view.
# - A "Public" principal has view access.
# - A separate "Finance Committee" packet with its own ACL.
SEED_ROWS = [
    {
        # Superintendent: full manage access on January 2024 board packet
        "id": "804cecfc-5f45-4a84-9d16-6a2494a5dfaf",
        "resource_type": "document",
        "resource_id": "e0c6ecb5-af4d-5c1c-bc1b-bf266b3ba7d8",  # Jan 2024 board packet
        "principal_type": "user",
        "principal_id": "de036046-aeed-4e84-960c-07ca8f9b99b9",  # Superintendent user
        "permission": "manage",
        "created_at": "2024-01-01T01:00:00Z",
        "updated_at": "2024-01-01T01:00:00Z",
    },
    {
        # Board secretary: can edit and upload attachments
        "id": "9b0a8490-5354-48f4-bbf0-4fb4daaab86e",
        "resource_type": "document",
        "resource_id": "e0c6ecb5-af4d-5c1c-bc1b-bf266b3ba7d8",
        "principal_type": "user",
        "principal_id": "7846174e-6bf9-5887-9093-1018becbaeda",  # Board secretary
        "permission": "edit",
        "created_at": "2024-01-01T02:00:00Z",
        "updated_at": "2024-01-01T02:00:00Z",
    },
    {
        # All board members: read-only access to packet
        "id": "22467c39-780a-48fb-8b86-7e254b07a54f",
        "resource_type": "document",
        "resource_id": "e0c6ecb5-af4d-5c1c-bc1b-bf266b3ba7d8",
        "principal_type": "group",
        "principal_id": "b83452b8-0419-5695-99f9-c57039c4b698",  # Group: Board Members
        "permission": "view",
        "created_at": "2024-01-01T03:00:00Z",
        "updated_at": "2024-01-01T03:00:00Z",
    },
    {
        # Public: view access once the packet is published
        "id": "e39dd5c0-dad4-4edd-b33d-2f27185a720d",
        "resource_type": "document",
        "resource_id": "e0c6ecb5-af4d-5c1c-bc1b-bf266b3ba7d8",
        "principal_type": "role",
        "principal_id": "ec3b184f-0a9b-5eb9-b819-fedb3af66b7b",  # Role: public
        "permission": "view",
        "created_at": "2024-01-01T04:00:00Z",
        "updated_at": "2024-01-01T04:00:00Z",
    },
    {
        # Finance committee chair: manage a separate finance packet
        "id": "4b66803e-29fd-49c2-bb1f-4712cae5cb4c",
        "resource_type": "document",
        "resource_id": "29b6f89f-1d5a-5d65-a50f-2592e49a9f4a",  # Finance committee packet
        "principal_type": "user",
        "principal_id": "403edfcd-06c1-5f15-b033-b5a50d1bdfb8",  # Finance chair
        "permission": "manage",
        "created_at": "2024-01-01T05:00:00Z",
        "updated_at": "2024-01-01T05:00:00Z",
    },
]


def _coerce_value(col: sa.Column, raw):
    """Best-effort coercion from inline seed value to appropriate Python/DB value."""
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

    # Let DB handle UUID, JSONB, timestamptz, etc.
    return raw


def upgrade() -> None:
    """Insert inline seed rows into document_permissions."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(TABLE_NAME):
        log.warning("Table %s does not exist; skipping seed", TABLE_NAME)
        return

    metadata = sa.MetaData()
    table = sa.Table(TABLE_NAME, metadata, autoload_with=bind)

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

    log.info("Inserted %s inline rows into %s", inserted, TABLE_NAME)


def downgrade() -> None:
    # No-op downgrade; seed data is left in place.
    pass
