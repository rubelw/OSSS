from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB
from ._helpers import ts_cols

class CICProposalDocument(UUIDMixin, Base):
    __tablename__ = "cic_proposal_documents"

    proposal_id = sa.Column(GUID(), ForeignKey("cic_proposals.id", ondelete="CASCADE"), nullable=False)
    document_id = sa.Column(GUID(), ForeignKey("documents.id",    ondelete="SET NULL"))
    file_uri    = sa.Column(sa.Text)
    label       = sa.Column(sa.Text)

    created_at, updated_at = ts_cols()

    proposal = relationship("CICProposal", back_populates="documents")
