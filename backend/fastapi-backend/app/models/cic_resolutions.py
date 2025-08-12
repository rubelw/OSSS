from __future__ import annotations
from datetime import datetime, date
from typing import Optional
from sqlalchemy import Column, Text, Date, DateTime, Integer, Boolean, ForeignKey, UniqueConstraint, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.sql import text
from sqlalchemy.orm import relationship
import sqlalchemy as sa

from .base import Base

class CICResolution(Base):
    __tablename__ = "cic_resolutions"

    id = Column(PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    meeting_id = Column(PGUUID(as_uuid=True), ForeignKey("cic_meetings.id", ondelete="CASCADE"), nullable=False)
    title = Column(Text, nullable=False)
    summary = Column(Text, nullable=True)
    effective_date = Column(Date, nullable=True)
    status = Column(Text, nullable=True)  # adopted|rejected|tabled
    created_at = Column(DateTime(timezone=True), server_default=sa.text("now()"), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=sa.text("now()"), nullable=False)

    meeting = relationship("CICMeeting", back_populates="resolutions")
