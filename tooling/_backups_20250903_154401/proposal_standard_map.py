
from __future__ import annotations

from typing import Optional
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID


class ProposalStandardMap(UUIDMixin, Base):
    __tablename__ = "proposal_standard_map"

    proposal_id: Mapped[str] = mapped_column(GUID(), sa.ForeignKey("proposals.id", ondelete="CASCADE"), nullable=False, index=True)
    standard_id: Mapped[str] = mapped_column(GUID(), sa.ForeignKey("standards.id", ondelete="CASCADE"), nullable=False, index=True)
    strength: Mapped[Optional[int]] = mapped_column(sa.Integer)  # 0-100 or rubric-dependent
    notes: Mapped[Optional[str]] = mapped_column(sa.Text)

    proposal = relationship("Proposal", back_populates="alignments")
    standard = relationship("Standard")
