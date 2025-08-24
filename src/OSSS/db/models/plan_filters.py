from __future__ import annotations
import uuid

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class PlanFilter(UUIDMixin, Base):
    __tablename__ = "plan_filters"

    plan_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("plans.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    criteria: Mapped[Optional[dict]] = mapped_column(JSONB())

    plan: Mapped["Plan"] = relationship("Plan", lazy="joined")

    __table_args__ = (
        sa.Index("ix_plan_filters_plan", "plan_id"),
    )
