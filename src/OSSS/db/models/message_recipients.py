from __future__ import annotations

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class MessageRecipient(Base):
    __tablename__ = "message_recipients"

    message_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("messages.id", ondelete="CASCADE"), primary_key=True)
    person_id: Mapped[Any] = mapped_column(GUID(), ForeignKey("persons.id", ondelete="CASCADE"), primary_key=True)
    delivery_status: Mapped[Optional[str]] = mapped_column(sa.Text)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(sa.DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)
