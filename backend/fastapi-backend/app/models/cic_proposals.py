from __future__ import annotations
from datetime import datetime, date
from typing import Optional
from sqlalchemy import Column, CHAR, Text, Date, DateTime, Integer, Boolean, ForeignKey, UniqueConstraint, CheckConstraint
from sqlalchemy.sql import text
from sqlalchemy.orm import relationship
import sqlalchemy as sa

from .base import Base, GUID, UUIDMixin

class CICProposal(UUIDMixin, Base):
    __tablename__ = "cic_proposals"

    committee_id = Column(CHAR(36), ForeignKey("cic_committees.id", ondelete="CASCADE"), nullable=False)
    submitted_by_id = Column(CHAR(36), ForeignKey("persons.id", ondelete="SET NULL"), nullable=True)
    school_id = Column(CHAR(36), ForeignKey("schools.id", ondelete="SET NULL"), nullable=True)
    type = Column(Text, nullable=False)  # new_course|course_change|materials_adoption|policy
    subject_id = Column(CHAR(36), ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True)
    course_id = Column(CHAR(36), ForeignKey("courses.id", ondelete="SET NULL"), nullable=True)
    title = Column(Text, nullable=False)
    rationale = Column(Text, nullable=True)
    status = Column(Text, nullable=False, server_default=text("'draft'"))  # draft|under_review|approved|rejected|withdrawn
    submitted_at = Column(DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False)
    review_deadline = Column(Date, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False)

    committee = relationship("CICCommittee", back_populates="proposals")
    reviews = relationship("CICProposalReview", back_populates="proposal", cascade="all, delete-orphan")
    documents = relationship("CICProposalDocument", back_populates="proposal", cascade="all, delete-orphan")
