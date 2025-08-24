from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class BusStopTime(UUIDMixin, Base):
    __tablename__ = "bus_stop_times"

    route_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("bus_routes.id", ondelete="CASCADE"), nullable=False)
    stop_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("bus_stops.id", ondelete="CASCADE"), nullable=False)
    arrival_time: Mapped[time] = mapped_column(sa.Time, nullable=False)
    departure_time: Mapped[Optional[time]] = mapped_column(sa.Time)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)

    __table_args__ = (UniqueConstraint("route_id", "stop_id", "arrival_time", name="uq_bus_stop_time"),)
