from __future__ import annotations
from datetime import datetime, date
from typing import Optional
from sqlalchemy import Column, Text, CHAR, Date, DateTime, Integer, Boolean, ForeignKey, UniqueConstraint, CheckConstraint
from sqlalchemy.sql import text
from sqlalchemy.orm import relationship
import sqlalchemy as sa

from .base import Base, GUID, UUIDMixin

class CICMeeting(UUIDMixin, Base):
    __tablename__ = "cic_meetings"

    committee_id = Column(CHAR(36), ForeignKey("cic_committees.id", ondelete="CASCADE"), nullable=False)
    title = Column(Text, nullable=False)
    scheduled_at = Column(DateTime(timezone=True), nullable=False)
    ends_at = Column(DateTime(timezone=True), nullable=True)
    location = Column(Text, nullable=True)
    status = Column(Text, nullable=False, server_default=text("'scheduled'"))
    is_public = Column(Boolean, nullable=False, server_default=text("true"))
    created_at = Column(DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False)

    committee = relationship("CICCommittee", back_populates="meetings")
    agenda_items = relationship("CICAgendaItem", back_populates="meeting", cascade="all, delete-orphan")
    resolutions = relationship("CICResolution", back_populates="meeting", cascade="all, delete-orphan")
    publications = relationship("CICPublication", back_populates="meeting", cascade="all, delete-orphan")
    meeting_documents = relationship("CICMeetingDocument", back_populates="meeting", cascade="all, delete-orphan")
