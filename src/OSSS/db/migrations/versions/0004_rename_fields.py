# src/OSSS/db/migrations/versions/0005_seed_tables.py
from __future__ import annotations

import json
import os
import uuid
from typing import Any, Iterable
import logging

from alembic import op, context
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as psql

from sqlalchemy import Table, MetaData
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError, ProgrammingError, DataError
from sqlalchemy.dialects.postgresql import insert as pg_insert

# add these near your other imports
from uuid import uuid4
from sqlalchemy.orm import Session

from datetime import datetime, date, timezone, time
from sqlalchemy.dialects.postgresql import UUID as PGUUID, TSVECTOR  # keep PGUUID; add TSVECTOR
from sqlalchemy.orm import Session


# ---- Alembic identifiers ----
revision = "0004_rename_fields"
down_revision = "0003_add_updated_at_to_users"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

TSVECTOR_CREATED_AT_TABLES = [
    "requirements",
    "education_associations",
    "meetings",
    "alignments",
    "approvals",
    "curricula",
    "curriculum_versions",
    "proposals",
    "review_requests",
]


def upgrade():
    for t in TSVECTOR_CREATED_AT_TABLES:
        # 1) rename existing tsvector column
        op.alter_column(
            t,
            "created_at",
            new_column_name="created_at_tsv",
            existing_type=psql.TSVECTOR(),
        )

        # 2) add a normal timestamptz created_at
        op.add_column(
            t,
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
        )


def downgrade():
    for t in TSVECTOR_CREATED_AT_TABLES:
        # drop real created_at
        op.drop_column(t, "created_at")

        # rename tsvector back (if you really want)
        op.alter_column(
            t,
            "created_at_tsv",
            new_column_name="created_at",
            existing_type=psql.TSVECTOR(),
        )