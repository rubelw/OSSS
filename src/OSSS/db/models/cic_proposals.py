from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB
from ._helpers import ts_cols

class CICProposal(UUIDMixin, Base):
    __tablename__ = "cic_proposals"

    committee_id   = sa.Column(GUID(), ForeignKey("cic_committees.id", ondelete="CASCADE"), nullable=False)
    submitted_by_id= sa.Column(GUID(), ForeignKey("persons.id",        ondelete="SET NULL"))
    school_id      = sa.Column(GUID(), ForeignKey("schools.id",        ondelete="SET NULL"))
    type           = sa.Column(sa.Text, nullable=False)  # new_course|course_change|materials_adoption|policy
    subject_id     = sa.Column(GUID(), ForeignKey("subjects.id", ondelete="SET NULL"))
    course_id      = sa.Column(GUID(), ForeignKey("courses.id",  ondelete="SET NULL"))
    title          = sa.Column(sa.Text, nullable=False)
    rationale      = sa.Column(sa.Text)
    status         = sa.Column(sa.Text, nullable=False, server_default=text("'draft'"))  # draft|under_review|approved|rejected|withdrawn
    submitted_at   = sa.Column(sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now())

    created_at, updated_at = ts_cols()

    committee = relationship("CICCommittee", back_populates="proposals")
    reviews   = relationship("CICProposalReview",   back_populates="proposal", cascade="all, delete-orphan")
    documents = relationship("CICProposalDocument", back_populates="proposal", cascade="all, delete-orphan")
