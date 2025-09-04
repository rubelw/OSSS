from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class Message(UUIDMixin, Base):
    __tablename__ = "messages"

    sender_id: Mapped[Optional[Any]] = mapped_column(GUID(), ForeignKey("user_accounts.id", ondelete="SET NULL"))
    channel: Mapped[str] = mapped_column(sa.Text, nullable=False)
    subject: Mapped[Optional[str]] = mapped_column(sa.Text)
    body: Mapped[Optional[str]] = mapped_column(sa.Text)
    sent_at: Mapped[Optional[datetime]] = mapped_column(sa.DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)
