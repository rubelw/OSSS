from __future__ import annotations
import uuid

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class KPIDatapoint(UUIDMixin, Base):
    __tablename__ = "kpi_datapoints"

    kpi_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("kpis.id", ondelete="CASCADE"), nullable=False
    )
    as_of: Mapped[date] = mapped_column(sa.Date, nullable=False)
    value: Mapped[float] = mapped_column(sa.Float, nullable=False)
    note: Mapped[Optional[str]] = mapped_column(sa.Text)

    kpi: Mapped["KPI"] = relationship("KPI", back_populates="datapoints", lazy="joined")

    __table_args__ = (
        sa.UniqueConstraint("kpi_id", "as_of", name="uq_kpi_datapoint"),
        sa.Index("ix_kpi_datapoints_kpi", "kpi_id"),
    )
