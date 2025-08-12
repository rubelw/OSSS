from __future__ import annotations
from datetime import datetime, date
from typing import Optional
from sqlalchemy import Column, Text, Date, DateTime, Integer, Boolean, ForeignKey, UniqueConstraint, CheckConstraint
from sqlalchemy.sql import text
from sqlalchemy.orm import relationship
import sqlalchemy as sa

from .base import Base, GUID, UUIDMixin

class CICCommittee(UUIDMixin, Base):
    __tablename__ = "cic_committees"

    district_id = sa.Column(sa.CHAR(36), ForeignKey("districts.id", ondelete="SET NULL"), nullable=True)
    school_id = sa.Column(sa.CHAR(36), ForeignKey("schools.id", ondelete="SET NULL"), nullable=True)
    name = sa.Column(Text, nullable=False)
    description = sa.Column(Text, nullable=True)
    status = sa.Column(Text, nullable=False, server_default=text("'active'"))
    created_at = Column(DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False)

    __table_args__ = (
        CheckConstraint("(district_id IS NOT NULL) OR (school_id IS NOT NULL)", name="ck_cic_committee_scope"),
    )

    memberships = relationship("CICMembership", back_populates="committee", cascade="all, delete-orphan")
    meetings = relationship("CICMeeting", back_populates="committee", cascade="all, delete-orphan")
    proposals = relationship("CICProposal", back_populates="committee", cascade="all, delete-orphan")
