from __future__ import annotations
from datetime import datetime, date
from typing import Optional
from sqlalchemy import Column, Text, CHAR, Date, DateTime, Integer, Boolean, ForeignKey, UniqueConstraint, CheckConstraint
from sqlalchemy.sql import text
from sqlalchemy.orm import relationship
import sqlalchemy as sa

from .base import Base, GUID, UUIDMixin

class CICProposalReview(UUIDMixin, Base):
    __tablename__ = "cic_proposal_reviews"

    proposal_id = Column(CHAR(36), ForeignKey("cic_proposals.id", ondelete="CASCADE"), nullable=False)
    reviewer_id = Column(CHAR(36), ForeignKey("persons.id", ondelete="SET NULL"), nullable=True)
    decision = Column(Text, nullable=True)  # approve|reject|revise
    decided_at = Column(DateTime(timezone=True), nullable=True)
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False)

    __table_args__ = (
        UniqueConstraint("proposal_id", "reviewer_id", name="uq_cic_proposal_reviewer"),
    )

    proposal = relationship("CICProposal", back_populates="reviews")
