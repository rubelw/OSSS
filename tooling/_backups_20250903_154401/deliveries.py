from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class Delivery(UUIDMixin, Base):
    __tablename__ = "deliveries"

    post_id: Mapped[str] = mapped_column(GUID(), ForeignKey("posts.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[str] = mapped_column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(sa.TIMESTAMP(timezone=True))
    medium: Mapped[Optional[str]] = mapped_column(sa.String(16))  # email|push|rss
    status: Mapped[Optional[str]] = mapped_column(sa.String(16))  # sent|failed|opened

    # Relationships
    post: Mapped["Post"] = relationship("Post", back_populates="deliveries")
