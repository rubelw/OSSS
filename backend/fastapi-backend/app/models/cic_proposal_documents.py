from __future__ import annotations
from datetime import datetime, date
from typing import Optional
from sqlalchemy import Column, Text, Date, DateTime, Integer, Boolean, ForeignKey, UniqueConstraint, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.sql import text
from sqlalchemy.orm import relationship
import sqlalchemy as sa

from .base import Base

class CICProposalDocument(Base):
    __tablename__ = "cic_proposal_documents"

    id = Column(PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    proposal_id = Column(PGUUID(as_uuid=True), ForeignKey("cic_proposals.id", ondelete="CASCADE"), nullable=False)
    document_id = Column(PGUUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
    file_uri = Column(Text, nullable=True)
    label = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=sa.text("now()"), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=sa.text("now()"), nullable=False)

    proposal = relationship("CICProposal", back_populates="documents")
