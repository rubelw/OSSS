# src/OSSS/db/models/donations.py
from __future__ import annotations

from datetime import datetime
import sqlalchemy as sa
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID
from .fundraising_campaigns import FundraisingCampaign


class Donation(UUIDMixin, Base):
    __tablename__ = "donations"
    __table_args__ = (
        sa.CheckConstraint("amount_cents >= 0", name="ck_donation_amount_nonneg"),
    )

    campaign_id:  Mapped[str]         = mapped_column(GUID(), ForeignKey("fundraising_campaigns.id", ondelete="CASCADE"), nullable=False, index=True)
    donor_name:   Mapped[str | None]  = mapped_column(sa.String(255))
    donor_email:  Mapped[str | None]  = mapped_column(sa.String(255))
    amount_cents: Mapped[int]         = mapped_column(sa.Integer, nullable=False)
    method:       Mapped[str | None]  = mapped_column(sa.String(64))   # cash, card, check, online
    donated_at:   Mapped[datetime]    = mapped_column(sa.DateTime, default=datetime.utcnow, nullable=False)
    receipt_code: Mapped[str | None]  = mapped_column(sa.String(64), unique=True)

    # relationships
    campaign: Mapped[FundraisingCampaign] = relationship("FundraisingCampaign", backref="donations")
