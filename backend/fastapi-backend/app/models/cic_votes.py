from __future__ import annotations
from datetime import datetime, date
from typing import Optional
from sqlalchemy import Column, Text, CHAR, Date, DateTime, Integer, Boolean, ForeignKey, UniqueConstraint, CheckConstraint
from sqlalchemy.sql import text
from sqlalchemy.orm import relationship
import sqlalchemy as sa

from .base import Base, GUID, UUIDMixin

class CICVote(UUIDMixin, Base):
    __tablename__ = "cic_votes"

    motion_id = Column(CHAR(36), ForeignKey("cic_motions.id", ondelete="CASCADE"), nullable=False)
    person_id = Column(CHAR(36), ForeignKey("persons.id", ondelete="CASCADE"), nullable=False)
    value = Column(Text, nullable=False)  # yea|nay|abstain|absent
    created_at = Column(DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False)

    __table_args__ = (
        UniqueConstraint("motion_id", "person_id", name="uq_cic_vote_unique"),
    )

    motion = relationship("CICMotion", back_populates="votes")
