from __future__ import annotations
from datetime import datetime, date
from typing import Optional
from sqlalchemy import Column, Text, Date, DateTime, Integer, Boolean, ForeignKey, UniqueConstraint, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.sql import text
from sqlalchemy.orm import relationship
import sqlalchemy as sa

from .base import Base

class CICVote(Base):
    __tablename__ = "cic_votes"

    id = Column(PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    motion_id = Column(PGUUID(as_uuid=True), ForeignKey("cic_motions.id", ondelete="CASCADE"), nullable=False)
    person_id = Column(PGUUID(as_uuid=True), ForeignKey("persons.id", ondelete="CASCADE"), nullable=False)
    value = Column(Text, nullable=False)  # yea|nay|abstain|absent
    created_at = Column(DateTime(timezone=True), server_default=sa.text("now()"), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=sa.text("now()"), nullable=False)

    __table_args__ = (
        UniqueConstraint("motion_id", "person_id", name="uq_cic_vote_unique"),
    )

    motion = relationship("CICMotion", back_populates="votes")
