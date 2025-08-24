from __future__ import annotations
import uuid

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB, TSVectorType

class MeetingSearchIndex(Base):
    __tablename__ = "meeting_search_index"

    meeting_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("meetings.id", ondelete="CASCADE"), primary_key=True
    )
    ts: Mapped[Optional[str]] = mapped_column(TSVectorType())

    __table_args__ = (
        sa.Index("ix_meeting_search_gin", "ts", postgresql_using="gin"),
    )
