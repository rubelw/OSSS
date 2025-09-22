from __future__ import annotations
from datetime import datetime
from typing import Optional

import sqlalchemy as sa
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID
from .concession_stands import ConcessionStand
from .events import Event   # <-- add this

class ConcessionSale(UUIDMixin, Base):
    __tablename__ = "concession_sales"

    stand_id: Mapped[str] = mapped_column(GUID(), ForeignKey("concession_stands.id"), nullable=False)
    event_id: Mapped[str | None] = mapped_column(GUID(), ForeignKey("events.id"))
    total_cents: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    sold_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=sa.func.now())

    stand: Mapped[ConcessionStand] = relationship()
    event: Mapped[Optional[Event]] = relationship()   # <-- Optional now resolves
