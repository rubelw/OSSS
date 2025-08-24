from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List
import uuid
import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class KPI(UUIDMixin, Base):
    __tablename__ = "kpis"

    goal_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(), ForeignKey("goals.id", ondelete="SET NULL")
    )
    objective_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(), ForeignKey("objectives.id", ondelete="SET NULL")
    )
    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    unit: Mapped[Optional[str]] = mapped_column(sa.String(32))
    target: Mapped[Optional[float]] = mapped_column(sa.Float)
    baseline: Mapped[Optional[float]] = mapped_column(sa.Float)
    direction: Mapped[Optional[str]] = mapped_column(sa.String(8))  # up|down

    goal: Mapped[Optional["Goal"]] = relationship("Goal", back_populates="kpis", lazy="joined")
    objective: Mapped[Optional["Objective"]] = relationship("Objective", back_populates="kpis", lazy="joined")

    datapoints: Mapped[List["KPIDatapoint"]] = relationship(
        "KPIDatapoint",
        back_populates="kpi",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="KPIDatapoint.as_of",
        lazy="selectin",
    )

    __table_args__ = (
        sa.Index("ix_kpis_goal", "goal_id"),
        sa.Index("ix_kpis_objective", "objective_id"),
    )
