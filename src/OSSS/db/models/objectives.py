from __future__ import annotations
import uuid

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class Objective(UUIDMixin, Base):
    __tablename__ = "objectives"

    goal_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("goals.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(sa.Text)

    goal: Mapped["Goal"] = relationship("Goal", back_populates="objectives", lazy="joined")

    initiatives: Mapped[List["Initiative"]] = relationship(
        "Initiative",
        back_populates="objective",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Initiative.name",
        lazy="selectin",
    )

    # KPIs attached to this Objective
    kpis: Mapped[List["KPI"]] = relationship(
        "KPI",
        back_populates="objective",
        primaryjoin="Objective.id == KPI.objective_id",
        lazy="selectin",
    )

    __table_args__ = (
        sa.Index("ix_objectives_goal", "goal_id"),
    )
