from __future__ import annotations
import uuid

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from OSSS.db.base import Base, UUIDMixin, GUID, JSONB

class DocumentNotification(Base):
    __tablename__ = "document_notifications"

    document_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    subscribed: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, server_default=sa.text("true"))
    last_sent_at: Mapped[Optional[datetime]] = mapped_column(sa.DateTime(timezone=True))

    document: Mapped["Document"] = relationship("Document", back_populates="notifications", lazy="joined")
