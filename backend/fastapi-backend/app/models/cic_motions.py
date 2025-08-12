from __future__ import annotations
from datetime import datetime, date
from typing import Optional
from sqlalchemy import Column, Text, Date, DateTime, Integer, Boolean, ForeignKey, UniqueConstraint, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.sql import text
from sqlalchemy.orm import relationship
import sqlalchemy as sa

from .base import Base

class CICMotion(Base):
    __tablename__ = "cic_motions"

    id = Column(PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    agenda_item_id = Column(PGUUID(as_uuid=True), ForeignKey("cic_agenda_items.id", ondelete="CASCADE"), nullable=False)
    text = Column(Text, nullable=False)
    moved_by_id = Column(PGUUID(as_uuid=True), ForeignKey("persons.id", ondelete="SET NULL"), nullable=True)
    seconded_by_id = Column(PGUUID(as_uuid=True), ForeignKey("persons.id", ondelete="SET NULL"), nullable=True)
    result = Column(Text, nullable=True)  # passed|failed|tabled
    tally_for = Column(Integer, nullable=True)
    tally_against = Column(Integer, nullable=True)
    tally_abstain = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=sa.text("now()"), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=sa.text("now()"), nullable=False)

    agenda_item = relationship("CICAgendaItem", back_populates="motions")
    votes = relationship("CICVote", back_populates="motion", cascade="all, delete-orphan")
