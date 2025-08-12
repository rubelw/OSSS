from __future__ import annotations
from datetime import datetime, date
from typing import Optional
from sqlalchemy import Column, Text, Date, DateTime, Integer, Boolean, ForeignKey, UniqueConstraint, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.sql import text
from sqlalchemy.orm import relationship
import sqlalchemy as sa

from .base import Base

class CICProposal(Base):
    __tablename__ = "cic_proposals"

    id = Column(PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    committee_id = Column(PGUUID(as_uuid=True), ForeignKey("cic_committees.id", ondelete="CASCADE"), nullable=False)
    submitted_by_id = Column(PGUUID(as_uuid=True), ForeignKey("persons.id", ondelete="SET NULL"), nullable=True)
    school_id = Column(PGUUID(as_uuid=True), ForeignKey("schools.id", ondelete="SET NULL"), nullable=True)
    type = Column(Text, nullable=False)  # new_course|course_change|materials_adoption|policy
    subject_id = Column(PGUUID(as_uuid=True), ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True)
    course_id = Column(PGUUID(as_uuid=True), ForeignKey("courses.id", ondelete="SET NULL"), nullable=True)
    title = Column(Text, nullable=False)
    rationale = Column(Text, nullable=True)
    status = Column(Text, nullable=False, server_default=text("'draft'"))  # draft|under_review|approved|rejected|withdrawn
    submitted_at = Column(DateTime(timezone=True), server_default=sa.text("now()"), nullable=False)
    review_deadline = Column(Date, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=sa.text("now()"), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=sa.text("now()"), nullable=False)

    committee = relationship("CICCommittee", back_populates="proposals")
    reviews = relationship("CICProposalReview", back_populates="proposal", cascade="all, delete-orphan")
    documents = relationship("CICProposalDocument", back_populates="proposal", cascade="all, delete-orphan")
