from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class Page(UUIDMixin, Base):
    __tablename__ = "pages"
    __table_args__ = (UniqueConstraint("channel_id", "slug", name="uq_pages_channel_slug"),)

    channel_id: Mapped[str] = mapped_column(GUID(), ForeignKey("channels.id", ondelete="CASCADE"), nullable=False)
    slug: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    title: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    body: Mapped[Optional[str]] = mapped_column(sa.Text)
    status: Mapped[str] = mapped_column(sa.String(16), nullable=False, server_default=sa.text("'draft'"))
    published_at: Mapped[Optional[datetime]] = mapped_column(sa.TIMESTAMP(timezone=True))

    # Relationships
    channel: Mapped["Channel"] = relationship("Channel", back_populates="pages")
