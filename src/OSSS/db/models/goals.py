from __future__ import annotations
import uuid

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class Goal(UUIDMixin, Base):
    __tablename__ = "goals"

    plan_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("plans.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(sa.Text)

    plan: Mapped["Plan"] = relationship("Plan", back_populates="goals", lazy="joined")

    objectives: Mapped[List["Objective"]] = relationship(
        "Objective",
        back_populates="goal",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Objective.name",
        lazy="selectin",
    )

    # KPIs attached directly to a Goal (optional; some KPIs may be for an Objective instead)
    kpis: Mapped[List["KPI"]] = relationship(
        "KPI",
        back_populates="goal",
        primaryjoin="Goal.id == KPI.goal_id",
        lazy="selectin",
    )

    __table_args__ = (
        sa.Index("ix_goals_plan", "plan_id"),
    )
