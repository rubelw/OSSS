from __future__ import annotations
from datetime import datetime, date
from typing import Optional
from sqlalchemy import Column, Text, Date, DateTime, Integer, Boolean, ForeignKey, UniqueConstraint, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.sql import text
from sqlalchemy.orm import relationship
import sqlalchemy as sa

from .base import Base

class CICMembership(Base):
    __tablename__ = "cic_memberships"

    id = Column(PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    committee_id = Column(PGUUID(as_uuid=True), ForeignKey("cic_committees.id", ondelete="CASCADE"), nullable=False)
    person_id = Column(PGUUID(as_uuid=True), ForeignKey("persons.id", ondelete="CASCADE"), nullable=False)
    role = Column(Text, nullable=True)  # chair, member, etc.
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    voting_member = Column(Boolean, nullable=False, server_default=text("true"))
    created_at = Column(DateTime(timezone=True), server_default=sa.text("now()"), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=sa.text("now()"), nullable=False)

    __table_args__ = (
        UniqueConstraint("committee_id", "person_id", name="uq_cic_membership_unique"),
    )

    committee = relationship("CICCommittee", back_populates="memberships")
