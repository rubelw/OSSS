from __future__ import annotations
import uuid

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB, TSVectorType

class PolicySearchIndex(Base):
    __tablename__ = "policy_search_index"

    policy_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("policies.id", ondelete="CASCADE"), primary_key=True
    )
    ts: Mapped[Optional[str]] = mapped_column(TSVectorType())

    __table_args__ = (
        sa.Index("ix_policy_search_gin", "ts", postgresql_using="gin"),
    )
