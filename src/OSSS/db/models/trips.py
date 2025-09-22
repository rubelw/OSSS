# src/OSSS/db/models/trip.py
from __future__ import annotations

from datetime import datetime
import sqlalchemy as sa
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID


class Trip(UUIDMixin, Base):
    __tablename__ = "trips"

    event_id:   Mapped[str]        = mapped_column(GUID(), ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True)
    provider:   Mapped[str | None] = mapped_column(sa.String(64))     # district, charter, parent
    bus_number: Mapped[str | None] = mapped_column(sa.String(64))
    driver_name: Mapped[str | None] = mapped_column(sa.String(128))
    depart_at:  Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True))
    return_at:  Mapped[datetime | None] = mapped_column(sa.TIMESTAMP(timezone=True))
    notes:      Mapped[str | None] = mapped_column(sa.Text)
    status:     Mapped[str | None] = mapped_column(sa.String(32))     # requested, booked, completed, canceled

    # relationships
    event: Mapped["Event"] = relationship("Event")
