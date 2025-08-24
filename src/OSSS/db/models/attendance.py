from __future__ import annotations
import uuid

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class Attendance(Base):
    __tablename__ = "attendance"

    meeting_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("meetings.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    status: Mapped[Optional[str]] = mapped_column(sa.String(16))
    arrived_at: Mapped[Optional[datetime]] = mapped_column(sa.TIMESTAMP(timezone=True))
    left_at: Mapped[Optional[datetime]] = mapped_column(sa.TIMESTAMP(timezone=True))

    meeting: Mapped["Meeting"] = relationship("Meeting", lazy="joined")
