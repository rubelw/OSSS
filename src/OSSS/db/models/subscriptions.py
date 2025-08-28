# OSSS/db/models/subscription.py
from __future__ import annotations
import sqlalchemy as sa
from sqlalchemy import ForeignKey, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from OSSS.db.base import Base, GUID

class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[str] = mapped_column(GUID(), primary_key=True, server_default=text("gen_random_uuid()"))

    channel_id:     Mapped[str] = mapped_column(GUID(), ForeignKey("channels.id", ondelete="CASCADE"), nullable=False, index=True)
    principal_type: Mapped[str] = mapped_column(sa.String(20), nullable=False)  # user|group|role
    principal_id:   Mapped[str] = mapped_column(GUID(), nullable=False, index=True)

    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.TIMESTAMP(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )

    channel = relationship("Channel", back_populates="subscriptions")

    __table_args__ = (
        sa.UniqueConstraint("channel_id", "principal_type", "principal_id", name="uq_subscriptions_tuple"),
        sa.Index("ix_subscriptions_principal", "principal_type", "principal_id"),
    )
