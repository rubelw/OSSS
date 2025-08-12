from __future__ import annotations
from datetime import datetime, date
from typing import Optional
from sqlalchemy import Column, Text, CHAR, Date, DateTime, Integer, Boolean, ForeignKey, UniqueConstraint, CheckConstraint
from sqlalchemy.sql import text
from sqlalchemy.orm import relationship
import sqlalchemy as sa

from .base import Base, GUID, UUIDMixin

class CICResolution(UUIDMixin, Base):
    __tablename__ = "cic_resolutions"

    meeting_id = Column(CHAR(36), ForeignKey("cic_meetings.id", ondelete="CASCADE"), nullable=False)
    title = Column(Text, nullable=False)
    summary = Column(Text, nullable=True)
    effective_date = Column(Date, nullable=True)
    status = Column(Text, nullable=True)  # adopted|rejected|tabled
    created_at = Column(DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False)

    meeting = relationship("CICMeeting", back_populates="resolutions")
