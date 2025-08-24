from __future__ import annotations
import uuid

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class ScorecardKPI(Base):
    __tablename__ = "scorecard_kpis"

    scorecard_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("scorecards.id", ondelete="CASCADE"), primary_key=True
    )
    kpi_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("kpis.id", ondelete="CASCADE"), primary_key=True
    )
    display_order: Mapped[Optional[int]] = mapped_column(sa.Integer)

    scorecard: Mapped["Scorecard"] = relationship("Scorecard", back_populates="kpi_links", lazy="joined")
    kpi: Mapped["KPI"] = relationship("KPI", lazy="joined")
