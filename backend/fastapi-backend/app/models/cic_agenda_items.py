from __future__ import annotations
from datetime import datetime, date
from typing import Optional
from sqlalchemy import Column, Text, CHAR, Date, DateTime, Integer, Boolean, ForeignKey, UniqueConstraint, CheckConstraint
from sqlalchemy.sql import text
from sqlalchemy.orm import relationship
import sqlalchemy as sa

from .base import Base, GUID, UUIDMixin

class CICAgendaItem(UUIDMixin, Base):
    __tablename__ = "cic_agenda_items"

    meeting_id = Column(CHAR(36), ForeignKey("cic_meetings.id", ondelete="CASCADE"), nullable=False)
    parent_id = Column(CHAR(36), ForeignKey("cic_agenda_items.id", ondelete="SET NULL"), nullable=True)
    position = Column(Integer, nullable=False, server_default=text("0"))
    title = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    time_allocated_minutes = Column(Integer, nullable=True)
    subject_id = Column(GUID(), ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True)
    course_id = Column(GUID(), ForeignKey("courses.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False)

    __table_args__ = (
        UniqueConstraint("meeting_id", "position", name="uq_cic_agenda_position"),
    )

    meeting = relationship("CICMeeting", back_populates="agenda_items")

    # ✅ FIX: reference the actual column via lambda; add explicit foreign_keys and inverse side
    parent = relationship(
        "CICAgendaItem",
        remote_side=lambda: [CICAgendaItem.id],
        back_populates="children",
        foreign_keys=lambda: [CICAgendaItem.parent_id],
    )
    children = relationship(
        "CICAgendaItem",
        back_populates="parent",
        cascade="all, delete-orphan",
        foreign_keys=lambda: [CICAgendaItem.parent_id],
        passive_deletes=True,
    )

    motions = relationship("CICMotion", back_populates="agenda_item", cascade="all, delete-orphan")
