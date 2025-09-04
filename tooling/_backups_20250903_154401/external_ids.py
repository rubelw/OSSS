# ----------------------------------------------------------------------
# ExternalId
#
# Purpose:
#   This table maps OSSS internal UUIDs to identifiers in external systems.
#   Schools typically use many systems (SIS, LMS, HR, State DOE, etc.),
#   each with its own ID schema. ExternalId acts as a cross-system identity
#   mapping layer so OSSS records can be matched to external records.
#
# Columns:
#   - entity_type : Type of record this ID belongs to (e.g., "student", "staff", "school", "course").
#   - entity_id   : OSSS internal UUID for the entity.
#   - system      : Which external system this ID is for (e.g., "SIS", "Google", "Canvas", "HR", "StateDOE").
#   - external_id : The identifier used in that external system.
#   - created_at  : Timestamp when the mapping was created.
#   - updated_at  : Timestamp when the mapping was last updated.
#
# Constraints:
#   - Unique per (entity_type, entity_id, system) so each OSSS record
#     has at most one mapping to a given external system.
#
# Example:
#   student | <uuid> | SIS      | 001234
#   student | <uuid> | Google   | john.smith@school.org
#   staff   | <uuid> | HR       | E12345
#   school  | <uuid> | StateDOE | HS-004
#
# Summary:
#   Use this table as the "bridge" between OSSS canonical IDs and
#   all external systems a district must integrate with.
# ----------------------------------------------------------------------

from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class ExternalId(UUIDMixin, Base):
    __tablename__ = "external_ids"

    entity_type: Mapped[str] = mapped_column(sa.Text, nullable=False)
    entity_id: Mapped[Any] = mapped_column(GUID(), nullable=False)
    system: Mapped[str] = mapped_column(sa.Text, nullable=False)
    external_id: Mapped[str] = mapped_column(sa.Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)

