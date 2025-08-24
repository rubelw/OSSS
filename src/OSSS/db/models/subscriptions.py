from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class Subscription(Base):
    __tablename__ = "subscriptions"

    channel_id: Mapped[str] = mapped_column(GUID(), ForeignKey("channels.id", ondelete="CASCADE"), primary_key=True)
    principal_type: Mapped[str] = mapped_column(sa.String(20), primary_key=True)  # user|group|role
    principal_id: Mapped[str] = mapped_column(GUID(), primary_key=True)

    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")
    )

    # Relationships
    channel: Mapped["Channel"] = relationship("Channel", back_populates="subscriptions")
