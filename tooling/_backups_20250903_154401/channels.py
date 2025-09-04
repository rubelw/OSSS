from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class Channel(UUIDMixin, Base):
    __tablename__ = "channels"

    org_id: Mapped[str] = mapped_column(GUID(), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    audience: Mapped[str] = mapped_column(sa.String(16), nullable=False, server_default=sa.text("'public'"))  # public|staff|board
    description: Mapped[Optional[str]] = mapped_column(sa.Text)

    # Relationships
    posts: Mapped[list["Post"]] = relationship(
        "Post",
        back_populates="channel",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    pages: Mapped[list["Page"]] = relationship(
        "Page",
        back_populates="channel",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    subscriptions: Mapped[list["Subscription"]] = relationship(
        "Subscription",
        back_populates="channel",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
