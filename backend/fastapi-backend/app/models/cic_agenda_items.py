from __future__ import annotations
from datetime import datetime, date
from typing import Optional
from sqlalchemy import Column, Text, Date, DateTime, Integer, Boolean, ForeignKey, UniqueConstraint, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.sql import text
from sqlalchemy.orm import relationship
import sqlalchemy as sa

from .base import Base

class CICAgendaItem(Base):
    __tablename__ = "cic_agenda_items"

    id = Column(PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    meeting_id = Column(PGUUID(as_uuid=True), ForeignKey("cic_meetings.id", ondelete="CASCADE"), nullable=False)
    parent_id = Column(PGUUID(as_uuid=True), ForeignKey("cic_agenda_items.id", ondelete="SET NULL"), nullable=True)
    position = Column(Integer, nullable=False, server_default=text("0"))
    title = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    time_allocated_minutes = Column(Integer, nullable=True)
    subject_id = Column(PGUUID(as_uuid=True), ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True)
    course_id = Column(PGUUID(as_uuid=True), ForeignKey("courses.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=sa.text("now()"), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=sa.text("now()"), nullable=False)

    __table_args__ = (
        UniqueConstraint("meeting_id", "position", name="uq_cic_agenda_position"),
    )

    meeting = relationship("CICMeeting", back_populates="agenda_items")
    parent = relationship("CICAgendaItem", remote_side=[id])
    motions = relationship("CICMotion", back_populates="agenda_item", cascade="all, delete-orphan")
