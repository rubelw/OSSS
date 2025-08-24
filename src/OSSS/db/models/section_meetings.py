from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class SectionMeeting(UUIDMixin, Base):
    __tablename__ = "section_meetings"

    section_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("course_sections.id", ondelete="CASCADE"), nullable=False)
    day_of_week: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    period_id: Mapped[Optional[Any]] = mapped_column(GUID(), ForeignKey("periods.id", ondelete="SET NULL"))
    room_id: Mapped[Optional[Any]] = mapped_column(GUID(), ForeignKey("rooms.id", ondelete="SET NULL"))

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)

    __table_args__ = (UniqueConstraint("section_id", "day_of_week", "period_id", name="uq_section_meeting"),)
