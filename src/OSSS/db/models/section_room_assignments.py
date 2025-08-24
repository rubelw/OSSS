from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class SectionRoomAssignment(UUIDMixin, Base):
    __tablename__ = "section_room_assignments"

    section_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("course_sections.id", ondelete="CASCADE"), nullable=False)
    room_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False)
    start_date: Mapped[Optional[date]] = mapped_column(sa.Date)
    end_date: Mapped[Optional[date]] = mapped_column(sa.Date)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)

    __table_args__ = (UniqueConstraint("section_id", "room_id", "start_date", name="uq_section_room_range"),)
