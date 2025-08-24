from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class RetentionRule(UUIDMixin, Base):
    __tablename__ = "retention_rules"

    entity_type: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    policy: Mapped[dict] = mapped_column(JSONB(), nullable=False)

    __table_args__ = (sa.Index("ix_retention_rules_entity", "entity_type"),)
