from __future__ import annotations
from datetime import datetime, date
from typing import Optional
from sqlalchemy import Column, Text, CHAR, Date, DateTime, Integer, Boolean, ForeignKey, UniqueConstraint, CheckConstraint
from sqlalchemy.sql import text
from sqlalchemy.orm import relationship
import sqlalchemy as sa

from .base import Base, GUID, UUIDMixin

class CICMeetingDocument(UUIDMixin, Base):
    __tablename__ = "cic_meeting_documents"

    meeting_id = Column(CHAR(36), ForeignKey("cic_meetings.id", ondelete="CASCADE"), nullable=False)
    document_id = Column(CHAR(36), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
    file_uri = Column(Text, nullable=True)
    label = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False)

    meeting = relationship("CICMeeting", back_populates="meeting_documents")
