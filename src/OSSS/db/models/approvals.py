
from __future__ import annotations

from typing import Optional
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, TimestampMixin, GUID


class Approval(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "approvals"
    __table_args__ = (sa.UniqueConstraint("proposal_id", "association_id", name="uq_approval_proposal_assoc"),)

    proposal_id: Mapped[str] = mapped_column(GUID(), sa.ForeignKey("proposals.id", ondelete="CASCADE"), nullable=False, index=True)
    association_id: Mapped[str] = mapped_column(GUID(), nullable=False, index=True)

    approved_at: Mapped[sa.DateTime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    expires_at: Mapped[Optional[sa.DateTime]] = mapped_column(sa.DateTime(timezone=True))
    status: Mapped[str] = mapped_column(sa.Enum("active", "expired", "revoked", name="approval_status", native_enum=False), nullable=False, server_default="active")

    proposal = relationship("Proposal", back_populates="approvals")
