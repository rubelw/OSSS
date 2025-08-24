from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB
from ._helpers import ts_cols

class CICProposalReview(UUIDMixin, Base):
    __tablename__ = "cic_proposal_reviews"

    proposal_id = sa.Column(GUID(), ForeignKey("cic_proposals.id", ondelete="CASCADE"), nullable=False)
    reviewer_id = sa.Column(GUID(), ForeignKey("persons.id",       ondelete="SET NULL"))
    decision    = sa.Column(sa.Text)  # approve|reject|revise
    decided_at  = sa.Column(sa.TIMESTAMP(timezone=True))
    comment     = sa.Column(sa.Text)

    created_at, updated_at = ts_cols()

    __table_args__ = (UniqueConstraint("proposal_id", "reviewer_id", name="uq_cic_proposal_reviewer"),)

    proposal = relationship("CICProposal", back_populates="reviews")
