from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class Post(UUIDMixin, Base):
    __tablename__ = "posts"

    channel_id: Mapped[str] = mapped_column(GUID(), ForeignKey("channels.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    body: Mapped[Optional[str]] = mapped_column(sa.Text)
    status: Mapped[str] = mapped_column(sa.String(16), nullable=False, server_default=sa.text("'draft'"))  # draft|scheduled|published
    publish_at: Mapped[Optional[datetime]] = mapped_column(sa.TIMESTAMP(timezone=True))
    author_id: Mapped[Optional[str]] = mapped_column(GUID(), ForeignKey("users.id"))

    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True), nullable=False,
        server_default=sa.text("CURRENT_TIMESTAMP"),
        onupdate=sa.text("CURRENT_TIMESTAMP"),
    )

    # Relationships
    channel: Mapped["Channel"] = relationship("Channel", back_populates="posts")
    attachments: Mapped[list["PostAttachment"]] = relationship(
        "PostAttachment",
        back_populates="post",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    deliveries: Mapped[list["Delivery"]] = relationship(
        "Delivery",
        back_populates="post",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
