from __future__ import annotations
from datetime import datetime, date
from typing import Optional
from sqlalchemy import Column, Text, Date, DateTime, Integer, Boolean, ForeignKey, UniqueConstraint, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.sql import text
from sqlalchemy.orm import relationship
import sqlalchemy as sa

from .base import Base

class CICCommittee(Base):
    __tablename__ = "cic_committees"

    id = Column(PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    district_id = Column(PGUUID(as_uuid=True), ForeignKey("districts.id", ondelete="SET NULL"), nullable=True)
    school_id = Column(PGUUID(as_uuid=True), ForeignKey("schools.id", ondelete="SET NULL"), nullable=True)
    name = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(Text, nullable=False, server_default=text("'active'"))
    created_at = Column(DateTime(timezone=True), server_default=sa.text("now()"), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=sa.text("now()"), nullable=False)

    __table_args__ = (
        CheckConstraint("(district_id IS NOT NULL) OR (school_id IS NOT NULL)", name="ck_cic_committee_scope"),
    )

    memberships = relationship("CICMembership", back_populates="committee", cascade="all, delete-orphan")
    meetings = relationship("CICMeeting", back_populates="committee", cascade="all, delete-orphan")
    proposals = relationship("CICProposal", back_populates="committee", cascade="all, delete-orphan")
