from __future__ import annotations
import uuid

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class Plan(UUIDMixin, Base):
    __tablename__ = "plans"

    org_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    cycle_start: Mapped[Optional[date]] = mapped_column(sa.Date)
    cycle_end: Mapped[Optional[date]] = mapped_column(sa.Date)
    status: Mapped[Optional[str]] = mapped_column(sa.String(32))

    goals: Mapped[List["Goal"]] = relationship(
        "Goal",
        back_populates="plan",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Goal.name",
        lazy="selectin",
    )

    # Optional: a single search row per plan
    search_index: Mapped[Optional["PlanSearchIndex"]] = relationship(
        "PlanSearchIndex",
        back_populates="plan",
        cascade="all, delete-orphan",
        uselist=False,
        passive_deletes=True,
    )

    __table_args__ = (
        sa.Index("ix_plans_org", "org_id"),
    )
