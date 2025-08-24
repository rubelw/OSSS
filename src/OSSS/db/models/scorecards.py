from __future__ import annotations
import uuid

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class Scorecard(UUIDMixin, Base):
    __tablename__ = "scorecards"

    plan_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("plans.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)

    plan: Mapped["Plan"] = relationship("Plan", lazy="joined")
    kpi_links: Mapped[List["ScorecardKPI"]] = relationship(
        "ScorecardKPI",
        back_populates="scorecard",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
    )

    __table_args__ = (
        sa.Index("ix_scorecards_plan", "plan_id"),
    )
