from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class CalendarDay(UUIDMixin, Base):
    __tablename__ = "calendar_days"

    calendar_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("calendars.id", ondelete="CASCADE"), nullable=False)
    date: Mapped[date] = mapped_column(sa.Date, nullable=False)
    day_type: Mapped[str] = mapped_column(sa.Text, nullable=False, server_default=text("'instructional'"))
    notes: Mapped[Optional[str]] = mapped_column(sa.Text)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)

    __table_args__ = (UniqueConstraint("calendar_id", "date", name="uq_calendar_day"),)
