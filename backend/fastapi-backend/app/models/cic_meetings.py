from __future__ import annotations
from datetime import datetime, date
from typing import Optional
from sqlalchemy import Column, Text, Date, DateTime, Integer, Boolean, ForeignKey, UniqueConstraint, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.sql import text
from sqlalchemy.orm import relationship
import sqlalchemy as sa

from .base import Base

class CICMeeting(Base):
    __tablename__ = "cic_meetings"

    id = Column(PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    committee_id = Column(PGUUID(as_uuid=True), ForeignKey("cic_committees.id", ondelete="CASCADE"), nullable=False)
    title = Column(Text, nullable=False)
    scheduled_at = Column(DateTime(timezone=True), nullable=False)
    ends_at = Column(DateTime(timezone=True), nullable=True)
    location = Column(Text, nullable=True)
    status = Column(Text, nullable=False, server_default=text("'scheduled'"))
    is_public = Column(Boolean, nullable=False, server_default=text("true"))
    created_at = Column(DateTime(timezone=True), server_default=sa.text("now()"), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=sa.text("now()"), nullable=False)

    committee = relationship("CICCommittee", back_populates="meetings")
    agenda_items = relationship("CICAgendaItem", back_populates="meeting", cascade="all, delete-orphan")
    resolutions = relationship("CICResolution", back_populates="meeting", cascade="all, delete-orphan")
    publications = relationship("CICPublication", back_populates="meeting", cascade="all, delete-orphan")
    meeting_documents = relationship("CICMeetingDocument", back_populates="meeting", cascade="all, delete-orphan")
